from app.agents.base import BaseScaffoldAgent
from app.agents.contracts import OperationsDecisionAgentInput
from app.core.enums import AgentStatus
from app.schemas.analysis import OperationPlan
from app.schemas.common import Conclusion, DataGap
from app.skills.operation_content import OperationContentSkill


class OperationsDecisionAgent(BaseScaffoldAgent[OperationsDecisionAgentInput, OperationPlan]):
    """Build an evidence-aware Demo plan and a policy-checked content playbook."""

    input_model = OperationsDecisionAgentInput
    output_model = OperationPlan

    def __init__(self, content_skill: OperationContentSkill | None = None) -> None:
        self.content_skill = content_skill or OperationContentSkill.from_default()
        super().__init__()

    def _run_stub(self, context: OperationsDecisionAgentInput) -> OperationPlan:
        evidence_ids = sorted(
            set(context.product_market_analysis.evidence_ids + context.user_insight.evidence_ids)
        )
        data_gaps = self._merge_gaps(
            context.product.data_gaps,
            context.product_market_analysis.data_gaps,
            context.user_insight.data_gaps,
        )
        if not evidence_ids:
            data_gaps = self._merge_gaps(
                data_gaps,
                [
                    DataGap(
                        code="decision_evidence_missing",
                        field="operation_plan",
                        reason="No product-market or user-insight evidence is available for the decision.",
                        required_for="evidence-grounded positioning and marketing claims",
                    )
                ],
            )

        product = context.product
        market = product.target_market or "the selected target market"
        audience = product.target_audience[0] if product.target_audience else "the intended buyer segment"
        value_focus = product.features[0] if product.features else "verified product attributes"
        evidence_note = (
            "Use the cited product and user evidence as the validation boundary."
            if evidence_ids
            else "Treat this as a profile-led hypothesis until product and user evidence is supplied."
        )
        positioning = (
            f"Position {product.name} for {audience} in {market} around {value_focus}. {evidence_note}"
        )

        conclusions = [
            Conclusion(
                conclusion=positioning,
                conclusion_type="recommendation",
                confidence=0.72 if evidence_ids else 0.35,
                evidence_ids=evidence_ids,
                data_gaps=[] if evidence_ids else data_gaps,
            )
        ]
        if product.target_market:
            conclusions.append(
                Conclusion(
                    conclusion=f"The user-selected target market is {product.target_market}.",
                    conclusion_type="user_input",
                    confidence=1.0,
                )
            )
        if product.target_price is not None:
            currency = f" {product.target_currency}" if product.target_currency else ""
            conclusions.append(
                Conclusion(
                    conclusion=f"The user target price is {product.target_price}{currency}.",
                    conclusion_type="user_input",
                    confidence=1.0,
                )
            )
        if data_gaps:
            conclusions.append(
                Conclusion(
                    conclusion=(
                        "Market, pricing, and audience claims remain limited to the supplied profile and cited "
                        "evidence; unresolved gaps must be shown in the final report."
                    ),
                    conclusion_type="data_limitation",
                    confidence=1.0,
                    data_gaps=data_gaps,
                )
            )

        content = self.content_skill.build(product=product, positioning=positioning)
        next_steps = [
            "ACTION: Validate the proposed positioning against current marketplace evidence before launch.",
            "ACTION: Confirm every product specification and compatibility statement before publishing.",
            "ACTION: Add structured competitor prices and review statistics before making numeric claims.",
            *content.as_next_steps(),
        ]

        statuses = {
            context.product_market_analysis.status,
            context.user_insight.status,
        }
        if AgentStatus.FAILED in statuses:
            status = AgentStatus.FAILED
        elif evidence_ids:
            status = AgentStatus.SUCCEEDED
        else:
            status = AgentStatus.INSUFFICIENT_EVIDENCE

        return OperationPlan(
            status=status,
            data_origin=product.data_origin,
            conclusions=conclusions,
            evidence_ids=evidence_ids,
            data_gaps=data_gaps,
            positioning=positioning,
            next_steps=next_steps,
            scaffold_note=(
                "Deterministic Demo operations rules v1 are active; model-backed optimization and real market "
                "execution remain outside the scaffold boundary."
            ),
        )

    @staticmethod
    def _merge_gaps(*groups: list[DataGap]) -> list[DataGap]:
        result: list[DataGap] = []
        seen: set[tuple[str, str, str, str | None]] = set()
        for gap in (item for group in groups for item in group):
            key = (gap.code, gap.field, gap.reason, gap.required_for)
            if key not in seen:
                seen.add(key)
                result.append(gap)
        return result
