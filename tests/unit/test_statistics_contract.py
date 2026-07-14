from decimal import Decimal

from app.agents.contracts import ProductMarketAgentInput, UserInsightAgentInput
from app.core.enums import AgentStatus, DataOrigin, ImplementationStatus
from app.statistics.contracts import StatisticsResult
from app.statistics.stub import ScaffoldStatisticsProvider
from tests.builders import build_demo_product


def test_scaffold_statistics_provider_returns_typed_insufficient_evidence() -> None:
    product = build_demo_product()

    result = ScaffoldStatisticsProvider().get_statistics(product=product)

    assert result == StatisticsResult(
        product_id=product.product_id,
        status=AgentStatus.INSUFFICIENT_EVIDENCE,
        data_origin=DataOrigin.DEMO,
        implementation_status=ImplementationStatus.SCAFFOLD,
        metrics={},
        evidence_ids=[],
        data_gaps=result.data_gaps,
    )
    assert result.data_gaps[0].code == "statistics_not_implemented"


def test_analysis_agent_inputs_require_the_same_statistics_contract() -> None:
    product = build_demo_product()
    statistics = StatisticsResult(
        product_id=product.product_id,
        status=AgentStatus.SUCCEEDED,
        data_origin=DataOrigin.DEMO,
        metrics={"demo_count": Decimal("3")},
    )

    market = ProductMarketAgentInput(product=product, evidence=[], statistics=statistics)
    insight = UserInsightAgentInput(product=product, evidence=[], statistics=statistics)

    assert market.statistics is statistics
    assert insight.statistics is statistics
