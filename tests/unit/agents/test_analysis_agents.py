from langchain_core.runnables import RunnableSequence

from app.agents.contracts import ProductMarketAgentInput, UserInsightAgentInput
from app.agents.product_market import ProductMarketAgent
from app.agents.user_insight import UserInsightAgent
from app.core.enums import AgentStatus, DataOrigin
from app.schemas.analysis import ProductMarketAnalysis, UserInsight
from app.schemas.product import ProductProfile
from tests.builders import build_scaffold_statistics


def test_analysis_agents_expose_typed_demo_scaffold_outputs(demo_product: ProductProfile) -> None:
    product_agent = ProductMarketAgent()
    insight_agent = UserInsightAgent()
    statistics = build_scaffold_statistics(demo_product)

    assert isinstance(product_agent.chain, RunnableSequence)
    assert isinstance(insight_agent.chain, RunnableSequence)

    market = product_agent.run(
        ProductMarketAgentInput(product=demo_product, evidence=[], statistics=statistics)
    )
    insight = insight_agent.run(
        UserInsightAgentInput(product=demo_product, evidence=[], statistics=statistics)
    )

    assert isinstance(market, ProductMarketAnalysis)
    assert isinstance(insight, UserInsight)
    assert market.status is AgentStatus.INSUFFICIENT_EVIDENCE
    assert insight.status is AgentStatus.INSUFFICIENT_EVIDENCE
    for output in (market, insight):
        assert output.data_origin is DataOrigin.DEMO
        assert output.implementation_status.value == "scaffold"


def test_analysis_agent_input_is_validated_by_pydantic(demo_product: ProductProfile) -> None:
    output = ProductMarketAgent().chain.invoke(
        {
            "product": demo_product.model_dump(),
            "evidence": [],
            "statistics": build_scaffold_statistics(demo_product).model_dump(),
        }
    )

    assert isinstance(output, ProductMarketAnalysis)
    assert output.data_gaps[0].code == "no_rag_evidence"
