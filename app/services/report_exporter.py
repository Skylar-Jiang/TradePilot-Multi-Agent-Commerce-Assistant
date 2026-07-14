import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.enums import AuditStatus, DataOrigin
from app.schemas.common import DataGap, utc_now
from app.schemas.report import DEMO_DISCLAIMER, FinalReport
from app.skills.operation_content import OperationContentSkill
from app.workflows.state import TradePilotState


class ReportExporter:
    def __init__(self, report_dir: Path, content_skill: OperationContentSkill | None = None) -> None:
        self.report_dir = report_dir
        self.content_skill = content_skill or OperationContentSkill.from_default()

    def export(self, state: TradePilotState) -> FinalReport:
        if state.audit_result is None:
            raise ValueError("audit result is required before report export")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        report_id = str(uuid4())
        json_path = (self.report_dir / f"{report_id}.json").resolve()
        markdown_path = (self.report_dir / f"{report_id}.md").resolve()
        sections = self._sections(state)
        origin = state.audit_result.data_origin
        report = FinalReport(
            report_id=report_id,
            run_id=state.run_id,
            version=max(1, state.report_version + 1),
            audit_status=state.audit_result.status,
            data_origin=origin,
            is_demo=origin is DataOrigin.DEMO,
            disclaimer=DEMO_DISCLAIMER,
            sections=sections,
            markdown_path=str(markdown_path),
            json_path=str(json_path),
            created_at=utc_now(),
        )
        json_path.write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(self._markdown(report), encoding="utf-8")
        return report

    def _sections(self, state: TradePilotState) -> dict[str, Any]:
        plan = state.operation_plan
        audit = state.audit_result
        if audit is None:
            raise ValueError("audit result is required before report export")
        content = self.content_skill.extract(plan.next_steps) if plan else None
        limitations = self._collect_gaps(state)
        actions = (
            [step.removeprefix("ACTION: ") for step in plan.next_steps if step.startswith("ACTION: ")]
            if plan
            else []
        )
        evidence_index = [
            {
                "evidence_id": item.evidence_id,
                "knowledge_type": item.knowledge_type.value,
                "source_name": item.source_name,
                "source_uri": item.source_uri,
                "excerpt": item.excerpt,
                "data_origin": item.data_origin.value,
            }
            for item in state.rag_evidence
        ]
        return {
            "executive_summary": {
                "product_name": state.product_profile.name,
                "target_market": state.target_market or state.product_profile.target_market,
                "positioning": plan.positioning if plan else "",
                "decision_status": plan.status.value if plan else None,
                "audit_status": audit.status.value,
                "manual_review_required": audit.manual_review_required,
                "evidence_count": len(evidence_index),
                "limitation_count": len(limitations),
            },
            "product_profile": state.product_profile.model_dump(mode="json"),
            "product_market_analysis": self._dump(state.product_market_analysis),
            "user_insight": self._dump(state.user_insight),
            "operation_plan": self._dump(plan),
            "content_playbook": content.as_dict() if content else None,
            "audit_result": audit.model_dump(mode="json"),
            "data_limitations": [gap.model_dump(mode="json") for gap in limitations],
            "evidence_index": evidence_index,
            "next_actions": actions,
        }

    @staticmethod
    def _collect_gaps(state: TradePilotState) -> list[DataGap]:
        groups = [
            state.data_gaps,
            state.product_profile.data_gaps,
            state.product_market_analysis.data_gaps if state.product_market_analysis else [],
            state.user_insight.data_gaps if state.user_insight else [],
            state.operation_plan.data_gaps if state.operation_plan else [],
        ]
        result: list[DataGap] = []
        seen: set[tuple[str, str, str, str | None]] = set()
        for gap in (item for group in groups for item in group):
            key = (gap.code, gap.field, gap.reason, gap.required_for)
            if key not in seen:
                seen.add(key)
                result.append(gap)
        return result

    @staticmethod
    def _dump(value: object) -> dict[str, object] | None:
        return value.model_dump(mode="json") if value is not None else None  # type: ignore[union-attr]

    @staticmethod
    def _markdown(report: FinalReport) -> str:
        sections = report.sections
        summary = sections["executive_summary"]
        plan = sections.get("operation_plan") or {}
        content = sections.get("content_playbook") or {}
        audit = sections.get("audit_result") or {}
        limitations = sections.get("data_limitations") or []
        evidence = sections.get("evidence_index") or []
        actions = sections.get("next_actions") or []

        lines = [
            "# TradePilot DEMO Operations Report",
            "",
            f"> {report.disclaimer}",
            "",
            f"- report_version: `{report.version}`",
            f"- data_origin: `{report.data_origin.value}`",
            "- implementation_status: `scaffold`",
            f"- audit_status: `{report.audit_status.value}`",
            "",
        ]
        if report.audit_status is AuditStatus.REJECTED or summary.get("manual_review_required"):
            lines.extend(
                [
                    "## Manual review required",
                    "",
                    "The bounded correction did not clear every blocking issue. Do not publish the draft until "
                    "the listed audit findings are resolved.",
                    "",
                ]
            )

        lines.extend(
            [
                "## Executive summary",
                "",
                f"- Product: {summary.get('product_name') or 'Not supplied'}",
                f"- Target market: {summary.get('target_market') or 'Not supplied'}",
                f"- Decision status: `{summary.get('decision_status') or 'not_available'}`",
                f"- Evidence references: {summary.get('evidence_count', 0)}",
                f"- Recorded limitations: {summary.get('limitation_count', 0)}",
                "",
                str(summary.get("positioning") or "No positioning recommendation is available."),
                "",
                "## Key conclusions",
                "",
            ]
        )
        conclusions = plan.get("conclusions", [])
        if conclusions:
            for conclusion in conclusions:
                evidence_ids = conclusion.get("evidence_ids") or []
                suffix = f" [evidence: {', '.join(evidence_ids)}]" if evidence_ids else ""
                lines.append(f"- {conclusion.get('conclusion', '')}{suffix}")
        else:
            lines.append("- No structured conclusions are available.")

        lines.extend(["", "## Content playbook", ""])
        if content:
            lines.extend(["### Product title", "", str(content.get("title") or ""), ""])
            lines.extend(["### Selling-point bullets", ""])
            lines.extend(f"- {bullet}" for bullet in content.get("bullets", []))
            lines.extend(["", "### Product description", "", str(content.get("description") or ""), ""])
            lines.extend(["### Advertising keywords", ""])
            lines.append(", ".join(content.get("keywords", [])))
            lines.extend(["", "### Customer-service drafts", ""])
            for name, text in content.get("customer_service", {}).items():
                lines.extend([f"#### {name.replace('_', ' ').title()}", "", str(text), ""])
        else:
            lines.extend(["No content bundle was generated.", ""])

        lines.extend(["## Evidence audit", "", f"Status: `{audit.get('status', 'not_available')}`", ""])
        issues = audit.get("issues") or []
        lines.extend(f"- {issue}" for issue in issues)
        if not issues:
            lines.append("- No blocking or warning issues were found.")

        lines.extend(["", "## Data limitations", ""])
        if limitations:
            lines.extend(f"- **{gap['field']}**: {gap['reason']}" for gap in limitations)
        else:
            lines.append("- No additional data gaps were recorded.")

        lines.extend(["", "## Evidence index", ""])
        if evidence:
            for item in evidence:
                lines.append(
                    f"- `{item['evidence_id']}` - {item['source_name']} "
                    f"({item['knowledge_type']}, {item['data_origin']}): {item['excerpt']}"
                )
        else:
            lines.append("- No evidence references were supplied.")

        lines.extend(["", "## Next actions", ""])
        lines.extend(f"{index}. {action}" for index, action in enumerate(actions, start=1))
        if not actions:
            lines.append("1. Resolve audit findings and add the missing evidence before publication.")
        lines.extend(
            [
                "",
                "## Scaffold boundary",
                "",
                "This report uses deterministic Demo rules. Real model execution, live-market validation, and "
                "production publishing remain outside the current scaffold.",
                "",
            ]
        )
        return "\n".join(lines)
