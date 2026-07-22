import difflib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.enums import ErrorCode
from app.core.exceptions import ResourceNotFoundError, TradePilotError
from app.db.repositories.sqlalchemy import SqlAlchemyAnalysisRepository
from app.schemas.common import utc_now
from app.schemas.report import FinalReport, ReportSupportRequest
from app.services.conversation_service import ConversationService
from app.services.report_exporter import ReportExporter

NUMBER_PATTERN = re.compile(r"(?<![\w-])\d+(?:\.\d+)?(?![\w-])")
FORBIDDEN_SCOPE_TEXT = ("当前商品用户反馈", "该商品用户普遍认为", "当前商品差评")
EDITABLE_SECTION_IDS = {
    "content-playbook",
    "next-actions",
    "prelaunch-considerations",
    "reasoned-hypotheses",
}


class ReportSupportService:
    def __init__(self, session: Session) -> None:
        self.reports = SqlAlchemyAnalysisRepository(session)
        self.conversations = ConversationService(session)

    def support(self, report_id: str, request: ReportSupportRequest) -> dict[str, Any]:
        report = self.reports.get_report(report_id)
        section_key = self._section_key(report, request.section_id)
        conversation_id = request.conversation_id or str(uuid4())
        common_metadata = {
            "action": request.action,
            "report_id": report.report_id,
            "report_version": report.version,
            "section_id": request.section_id,
        }
        self.conversations.add_message(
            conversation_id,
            role="user",
            content=request.message,
            metadata={
                **common_metadata,
                "replacement": request.replacement,
                "audit_decision": "pending",
            },
            conversation_metadata={
                "kind": "report_support",
                "run_id": report.run_id,
                "report_id": report.report_id,
            },
        )
        try:
            result = (
                self._explain(report, section_key, request.section_id, request.message)
                if request.action == "explain"
                else self._edit(report, section_key, request)
            )
        except TradePilotError as exc:
            self.conversations.add_message(
                conversation_id,
                role="assistant",
                content=exc.message,
                metadata={
                    **common_metadata,
                    "audit_decision": "rejected",
                    "error_code": exc.code.value,
                    "changed_section_ids": [],
                },
            )
            raise
        result["conversation_id"] = conversation_id
        self.conversations.add_message(
            conversation_id,
            role="assistant",
            content=str(result["response"]),
            metadata={
                **common_metadata,
                "result_report_id": result["report_id"],
                "evidence_ids": result.get("evidence_ids", []),
                "limitations": result.get("limitations", []),
                "changed_section_ids": result.get("changed_section_ids", []),
                "audit_decision": "accepted",
            },
        )
        return result

    def rollback(self, report_id: str, *, target_version: int, reason: str) -> FinalReport:
        current = self.reports.get_report(report_id)
        versions = self.reports.list_report_versions(current.run_id)
        latest = versions[-1]
        target = next((item for item in versions if item.version == target_version), None)
        if target is None:
            raise ResourceNotFoundError("report_version", f"{current.run_id}:{target_version}")
        changed_keys = [
            key
            for key in sorted(set(latest.sections) | set(target.sections))
            if latest.sections.get(key) != target.sections.get(key)
        ]
        changed_ids = [target.section_index[key].section_id for key in changed_keys]
        report = self._new_snapshot(
            source=target,
            version=latest.version + 1,
            parent_report_id=latest.report_id,
            changed_section_ids=changed_ids,
        )
        self._write(report)
        return self.reports.save_report_version(
            report,
            change={
                "action": "rollback",
                "reason": reason,
                "target_version": target_version,
                "changed_section_ids": changed_ids,
            },
        )

    def versions(self, report_id: str) -> list[FinalReport]:
        report = self.reports.get_report(report_id)
        return self.reports.list_report_versions(report.run_id)

    def history(self) -> list[dict[str, Any]]:
        return self.reports.list_report_history()

    def _explain(
        self,
        report: FinalReport,
        section_key: str,
        section_id: str,
        message: str,
    ) -> dict[str, Any]:
        evidence_ids = self._evidence_ids(report, report.sections[section_key])
        limitations = self._limitations(report)
        descriptor = report.section_index.get(section_key)
        section_title = descriptor.title if descriptor else section_id
        points = self._explanation_points(report.sections[section_key], message)
        limitation_points = self._readable_texts(limitations, limit=2)
        point_text = "\n".join(f"{index}. {item}" for index, item in enumerate(points, start=1))
        limitation_text = (
            "；".join(limitation_points)
            if limitation_points
            else "报告中没有记录额外限制，但结论仍应结合新品上线后的真实销售反馈复核。"
        )
        response = (
            f"第 {report.version} 版报告的「{section_title}」主要依据当前已保存的分析内容：\n"
            f"{point_text}\n"
            f"证据基础：该章节关联 {len(evidence_ids)} 条可追溯证据。\n"
            f"数据限制：{limitation_text}\n"
            "本次仅解释现有结论，没有修改报告内容。"
        )
        return {
            "response": response,
            "report_id": report.report_id,
            "report_version": report.version,
            "section_id": section_id,
            "evidence_ids": evidence_ids,
            "limitations": limitations,
            "changed_section_ids": [],
        }

    @classmethod
    def _explanation_points(cls, value: Any, message: str) -> list[str]:
        """Return concise report-grounded points, prioritizing the user's business topic."""
        normalized = message.casefold()
        focus_groups = (
            (("定价", "价格", "售价", "price", "pricing"), ("price", "pricing", "售价", "定价", "价格")),
            (("定位", "position"), ("position", "定位", "value_proposition")),
            (("用户", "客群", "受众", "persona", "segment"), ("audience", "persona", "segment", "用户", "客群")),
            (("渠道", "推广", "投放", "channel", "promotion"), ("channel", "promotion", "渠道", "推广", "投放")),
            (("文案", "传播", "message", "copy"), ("messaging", "copy", "文案", "传播")),
        )
        wanted_keys: tuple[str, ...] = ()
        for query_terms, keys in focus_groups:
            if any(term in normalized for term in query_terms):
                wanted_keys = keys
                break

        focused_values: list[Any] = []
        if wanted_keys:
            cls._values_for_matching_keys(value, wanted_keys, focused_values)
        points = cls._readable_texts(focused_values, limit=3)
        if not points:
            points = cls._readable_texts(value, limit=3)
        return points or ["该章节当前没有可进一步展开的文字结论，请结合报告中的结构化字段查看。"]

    @classmethod
    def _values_for_matching_keys(
        cls,
        value: Any,
        wanted_keys: tuple[str, ...],
        result: list[Any],
    ) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized_key = str(key).casefold()
                if any(wanted in normalized_key for wanted in wanted_keys):
                    result.append(item)
                else:
                    cls._values_for_matching_keys(item, wanted_keys, result)
        elif isinstance(value, list):
            for item in value:
                cls._values_for_matching_keys(item, wanted_keys, result)

    @classmethod
    def _readable_texts(cls, value: Any, *, limit: int) -> list[str]:
        ignored_keys = {
            "evidence_id",
            "evidence_ids",
            "source_uri",
            "parent_asin",
            "asin",
            "report_id",
            "run_id",
        }
        found: list[str] = []

        def visit(item: Any, key: str = "") -> None:
            if len(found) >= limit or key.casefold() in ignored_keys:
                return
            if isinstance(item, dict):
                for child_key, child in item.items():
                    visit(child, str(child_key))
                    if len(found) >= limit:
                        return
            elif isinstance(item, list):
                for child in item:
                    visit(child, key)
                    if len(found) >= limit:
                        return
            elif isinstance(item, str):
                text = " ".join(item.split()).strip(" ，。；")
                if not text or text in found or re.fullmatch(r"[A-Za-z0-9_-]{20,}", text):
                    return
                found.append(f"{text[:157]}…" if len(text) > 160 else text)

        visit(value)
        return found

    def _edit(
        self,
        report: FinalReport,
        section_key: str,
        request: ReportSupportRequest,
    ) -> dict[str, Any]:
        if request.section_id not in EDITABLE_SECTION_IDS:
            self._reject("This section is not eligible for localized support edits")
        if request.replacement is None:
            self._reject("replacement is required for an edit")
        replacement_text = json.dumps(request.replacement, ensure_ascii=False, sort_keys=True)
        if any(term in replacement_text for term in FORBIDDEN_SCOPE_TEXT):
            self._reject("The replacement misattributes peer-market evidence to the new product")
        source_text = json.dumps(report.sections, ensure_ascii=False, sort_keys=True)
        unseen_numbers = sorted(
            set(NUMBER_PATTERN.findall(replacement_text)) - set(NUMBER_PATTERN.findall(source_text))
        )
        if unseen_numbers:
            self._reject(f"Unsubstantiated numeric claims are not allowed: {', '.join(unseen_numbers)}")
        known_evidence = set(self._evidence_ids(report, report.sections))
        supplied_evidence = set(self._strings_for_key(request.replacement, "evidence_ids"))
        if supplied_evidence - known_evidence:
            self._reject("The replacement references unknown evidence IDs")
        latest = self.reports.get_latest_report(report.run_id)
        if latest.report_id != report.report_id:
            self._reject("Edits must target the latest report version")

        before = deepcopy(report.sections[section_key])
        sections = deepcopy(report.sections)
        sections[section_key] = request.replacement
        after = deepcopy(request.replacement)
        before_text = json.dumps(before, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
        after_text = json.dumps(after, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
        unified_diff = "\n".join(
            difflib.unified_diff(
                before_text,
                after_text,
                fromfile=f"version-{report.version}",
                tofile=f"version-{report.version + 1}",
                lineterm="",
            )
        )
        updated = self._new_snapshot(
            source=report.model_copy(update={"sections": sections}),
            version=report.version + 1,
            parent_report_id=report.report_id,
            changed_section_ids=[request.section_id],
        )
        self._write(updated)
        self.reports.save_report_version(
            updated,
            change={
                "action": "edit",
                "request": request.message,
                "section_id": request.section_id,
                "before": before,
                "after": after,
                "unified_diff": unified_diff,
                "audit_decision": "accepted",
            },
        )
        return {
            "response": f"Created report version {updated.version} with one localized section change.",
            "report_id": updated.report_id,
            "report_version": updated.version,
            "section_id": request.section_id,
            "evidence_ids": self._evidence_ids(report, request.replacement),
            "limitations": self._limitations(report),
            "changed_section_ids": updated.changed_section_ids,
            "before": before,
            "after": after,
            "unified_diff": unified_diff,
        }

    @staticmethod
    def _section_key(report: FinalReport, section_id: str) -> str:
        for key, descriptor in report.section_index.items():
            if descriptor.section_id == section_id:
                return key
        raise ResourceNotFoundError("report_section", section_id)

    @classmethod
    def _evidence_ids(cls, report: FinalReport, value: Any) -> list[str]:
        found = set(cls._strings_for_key(value, "evidence_ids"))
        found.update(cls._strings_for_key(value, "evidence_id"))
        if not found:
            index = report.sections.get("evidence_index") or (
                report.sections.get("data_limitations_and_evidence_index") or {}
            ).get("evidence_index", [])
            found.update(str(item["evidence_id"]) for item in index if item.get("evidence_id"))
        return sorted(found)

    @staticmethod
    def _strings_for_key(value: Any, wanted: str) -> list[str]:
        result: list[str] = []
        if isinstance(value, dict):
            for key, item in value.items():
                if key == wanted:
                    if isinstance(item, list):
                        result.extend(str(entry) for entry in item)
                    elif item:
                        result.append(str(item))
                else:
                    result.extend(ReportSupportService._strings_for_key(item, wanted))
        elif isinstance(value, list):
            for item in value:
                result.extend(ReportSupportService._strings_for_key(item, wanted))
        return result

    @staticmethod
    def _limitations(report: FinalReport) -> list[Any]:
        limitations = report.sections.get("data_limitations")
        if limitations is None:
            limitations = (report.sections.get("data_limitations_and_evidence_index") or {}).get(
                "limitations", []
            )
        return list(limitations or [])

    @staticmethod
    def _new_snapshot(
        *,
        source: FinalReport,
        version: int,
        parent_report_id: str,
        changed_section_ids: list[str],
    ) -> FinalReport:
        report_id = str(uuid4())
        directory = Path(source.json_path).parent
        return source.model_copy(
            update={
                "report_id": report_id,
                "version": version,
                "parent_report_id": parent_report_id,
                "changed_section_ids": changed_section_ids,
                "json_path": str((directory / f"{report_id}.json").resolve()),
                "markdown_path": str((directory / f"{report_id}.md").resolve()),
                "created_at": utc_now(),
            }
        )

    @staticmethod
    def _write(report: FinalReport) -> None:
        Path(report.json_path).write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        Path(report.markdown_path).write_text(
            ReportExporter._markdown_with_anchors(report),
            encoding="utf-8",
        )

    @staticmethod
    def _reject(message: str) -> None:
        raise TradePilotError(ErrorCode.VALIDATION_ERROR, message, 422)
