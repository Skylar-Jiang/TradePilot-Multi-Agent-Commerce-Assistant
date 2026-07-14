from langchain_core.runnables import RunnableSequence

from app.agents.contracts import EvidenceAuditAgentInput, OperationsDecisionAgentInput
from app.agents.evidence_audit import EvidenceAuditAgent
from app.agents.operations_decision import OperationsDecisionAgent
from app.core.enums import AuditStatus, DataOrigin
from app.schemas.analysis import AuditResult, OperationPlan
from app.schemas.product import ProductProfile
from tests.builders import build_market_analysis, build_user_insight


def test_decision_agents_expose_typed_demo_scaffold_outputs(demo_product: ProductProfile) -> None:
    operations_agent = OperationsDecisionAgent()
    audit_agent = EvidenceAuditAgent()

    assert isinstance(operations_agent.chain, RunnableSequence)
    assert isinstance(audit_agent.chain, RunnableSequence)

    plan = operations_agent.run(
        OperationsDecisionAgentInput(
            product=demo_product,
            product_market_analysis=build_market_analysis(),
            user_insight=build_user_insight(),
        )
    )
    audit = audit_agent.run(EvidenceAuditAgentInput(product=demo_product, operation_plan=plan))

    assert isinstance(plan, OperationPlan)
    assert isinstance(audit, AuditResult)
    assert audit.status is AuditStatus.PASS
    for output in (plan, audit):
        assert output.data_origin is DataOrigin.DEMO
        assert output.implementation_status.value == "scaffold"
