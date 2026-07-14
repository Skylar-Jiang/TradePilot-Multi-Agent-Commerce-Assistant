from __future__ import annotations

import json
import re

from app.agents.base import BaseScaffoldAgent
from app.agents.contracts import EvidenceAuditAgentInput
from app.core.enums import AgentStatus, AuditStatus, ImplementationStatus
from app.schemas.analysis import AuditResult
from app.schemas.common import Conclusion
from app.skills.operation_content import OperationContentSkill

FACTUAL_CONCLUSION_TYPES = {
    "evidence_grounded",
    "evidence_summary",
    "market_fact",
    "product_fact",
    "user_insight",
}

CONFLICT_PAIRS = (
    (("low price", "low-price", "budget", "低价"), ("premium", "high-end", "高端")),
    (("durable", "耐用"), ("fragile", "易碎")),
    (("compact", "便携", "小巧"), ("bulky", "笨重", "大体积")),
    (("safe for", "安全适用"), ("unsafe", "不安全")),
)


class EvidenceAuditAgent(BaseScaffoldAgent[EvidenceAuditAgentInput, AuditResult]):
    """Audit evidence binding, claim safety, conflicts, and content-policy compliance."""

    input_model = EvidenceAuditAgentInput
    output_model = AuditResult

    def __init__(self, content_skill: OperationContentSkill | None = None) -> None:
        self.content_skill = content_skill or OperationContentSkill.from_default()
        super().__init__()

    def _run_stub(self, context: EvidenceAuditAgentInput) -> AuditResult:
        plan = context.operation_plan
        blocking: list[str] = []
        warnings: list[str] = []
        unresolved: list[str] = []
        conflicting_evidence_ids: list[str] = []

        if plan.data_origin is not context.product.data_origin:
            blocking.append(
                "data_origin_mismatch: Regenerate the plan using only data from the current product mode; "
                f"product={context.product.data_origin.value}, plan={plan.data_origin.value}."
            )
        if plan.implementation_status is not ImplementationStatus.SCAFFOLD:
            blocking.append(
                "implementation_status_invalid: Preserve the scaffold marker until the shared contract changes."
            )
        if plan.status is AgentStatus.FAILED:
            blocking.append("operation_plan_failed: Resolve the decision Agent failure before report export.")

        declared_evidence = set(plan.evidence_ids)
        if len(declared_evidence) != len(plan.evidence_ids):
            warnings.append("duplicate_evidence_ids: De-duplicate operation_plan.evidence_ids.")

        for index, conclusion in enumerate(plan.conclusions):
            unknown_ids = sorted(set(conclusion.evidence_ids).difference(declared_evidence))
            if unknown_ids:
                conflicting_evidence_ids.extend(unknown_ids)
                blocking.append(
                    f"conclusion[{index}].evidence_ids: {', '.join(unknown_ids)} are not declared by the plan; "
                    "bind available evidence or remove the unsupported references."
                )
            if (
                conclusion.conclusion_type in FACTUAL_CONCLUSION_TYPES
                and not conclusion.evidence_ids
                and not conclusion.data_gaps
            ):
                blocking.append(
                    f"conclusion[{index}].unsupported_fact: Bind evidence or downgrade the claim to a "
                    "recommendation with an explicit data gap."
                )
            if (
                conclusion.conclusion_type == "recommendation"
                and not conclusion.evidence_ids
                and not conclusion.data_gaps
            ):
                warnings.append(
                    f"conclusion[{index}].uncaveated_recommendation: Add supporting evidence or an explicit "
                    "limitation."
                )

        content = self.content_skill.extract(plan.next_steps)
        for issue in self.content_skill.audit(content):
            message = f"{issue.code}: {issue.message}"
            (blocking if issue.blocking else warnings).append(message)

        plan_text = self._plan_text(context).casefold()
        for claim in self.content_skill.config.rules.forbidden_claims:
            if claim.casefold() in plan_text:
                blocking.append(
                    "forbidden_plan_claim: Remove the unsupported or prohibited expression "
                    f"{claim!r} from positioning, conclusions, or next actions."
                )

        numeric_issues = self._unverified_numeric_claims(context)
        blocking.extend(numeric_issues)

        conflict_messages, conflict_ids = self._semantic_conflicts(plan.conclusions, plan.positioning)
        blocking.extend(conflict_messages)
        conflicting_evidence_ids.extend(conflict_ids)

        risk_issues = self._risk_conflicts(context)
        blocking.extend(risk_issues)

        if context.product.target_market and context.product.target_market.casefold() not in plan_text:
            warnings.append(
                "target_market_missing: Include the user-selected target market in positioning or next actions."
            )

        for gap in plan.data_gaps:
            unresolved.append(f"{gap.field}: {gap.reason}")

        blocking = self._unique(blocking)
        warnings = self._unique(warnings)
        unresolved = self._unique(unresolved)
        conflicting_evidence_ids = self._unique(conflicting_evidence_ids)
        if blocking:
            status = AuditStatus.REJECTED
        elif warnings:
            status = AuditStatus.WARNING
        else:
            status = AuditStatus.PASS
        return AuditResult(
            status=status,
            data_origin=plan.data_origin,
            issues=[*blocking, *warnings],
            conflicting_evidence_ids=conflicting_evidence_ids,
            unresolved_questions=unresolved,
            manual_review_required=bool(blocking),
        )

    def _unverified_numeric_claims(self, context: EvidenceAuditAgentInput) -> list[str]:
        allowed_text = json.dumps(context.product.model_dump(mode="json"), ensure_ascii=False, default=str)
        allowed_numbers = set(re.findall(r"(?<![\w-])\d+(?:\.\d+)?%?(?![\w-])", allowed_text))
        issues: list[str] = []
        for label, text, conclusion_type in self._claim_texts(context):
            if conclusion_type == "user_input":
                continue
            for value in re.findall(r"(?<![\w-])\d+(?:\.\d+)?%?(?![\w-])", text):
                if value not in allowed_numbers:
                    issues.append(
                        f"{label}.unverified_numeric_claim: Remove {value!r} or bind it to validated structured "
                        "statistics/user input."
                    )
        return issues

    @staticmethod
    def _semantic_conflicts(
        conclusions: list[Conclusion], positioning: str
    ) -> tuple[list[str], list[str]]:
        records = [("positioning", positioning, [])]
        records.extend(
            (f"conclusion[{index}]", conclusion.conclusion, conclusion.evidence_ids)
            for index, conclusion in enumerate(conclusions)
        )
        messages: list[str] = []
        evidence_ids: list[str] = []
        for left_terms, right_terms in CONFLICT_PAIRS:
            left_records = [record for record in records if any(term in record[1].casefold() for term in left_terms)]
            right_records = [record for record in records if any(term in record[1].casefold() for term in right_terms)]
            if left_records and right_records:
                left_labels = ", ".join(record[0] for record in left_records)
                right_labels = ", ".join(record[0] for record in right_records)
                messages.append(
                    "semantic_conflict: Resolve opposing positioning claims between "
                    f"{left_labels} and {right_labels}; keep one interpretation and cite its evidence."
                )
                evidence_ids.extend(
                    evidence_id
                    for record in [*left_records, *right_records]
                    for evidence_id in record[2]
                )
        return messages, evidence_ids

    def _risk_conflicts(self, context: EvidenceAuditAgentInput) -> list[str]:
        text = self._plan_text(context).casefold()
        issues: list[str] = []
        for risk in context.product.known_risks:
            normalized = risk.casefold().strip()
            if normalized and (f"no {normalized}" in text or f"{normalized}-free" in text):
                issues.append(
                    f"known_risk_conflict: The plan denies the declared risk {risk!r}; replace the denial with "
                    "a verified limitation or mitigation."
                )
        return issues

    @staticmethod
    def _claim_texts(
        context: EvidenceAuditAgentInput,
    ) -> list[tuple[str, str, str | None]]:
        plan = context.operation_plan
        values: list[tuple[str, str, str | None]] = [("positioning", plan.positioning, None)]
        values.extend(
            (f"conclusion[{index}]", conclusion.conclusion, conclusion.conclusion_type)
            for index, conclusion in enumerate(plan.conclusions)
        )
        values.extend((f"next_steps[{index}]", step, None) for index, step in enumerate(plan.next_steps))
        return values

    def _plan_text(self, context: EvidenceAuditAgentInput) -> str:
        return "\n".join(text for _, text, _ in self._claim_texts(context))

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))
