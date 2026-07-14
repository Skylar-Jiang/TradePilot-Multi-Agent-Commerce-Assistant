from threading import Barrier

from app.agents.evidence_audit import EvidenceAuditAgent
from app.agents.operations_decision import OperationsDecisionAgent
from app.agents.product_market import ProductMarketAgent
from app.agents.user_insight import UserInsightAgent
from app.core.enums import AgentStatus, AuditStatus, DataMode, DataOrigin
from app.rag.in_memory import InMemoryKnowledgeStore
from app.schemas.analysis import AuditResult, OperationPlan, ProductMarketAnalysis, UserInsight
from app.schemas.product import ProductCreate, ProductProfile
from app.statistics.contracts import StatisticsResult
from app.workflows.graph import TradePilotWorkflow
from app.workflows.state import TradePilotState


def initial_state() -> TradePilotState:
    product = ProductProfile(
        product_id="product-1",
        data_origin=DataOrigin.DEMO,
        **ProductCreate(
            name=" DEMO Portable Organizer ",
            category="demo-generic",
            data_mode=DataMode.DEMO,
        ).model_dump(),
    )
    return TradePilotState(
        task_id="task-1",
        run_id="run-1",
        session_id="session-1",
        thread_id="thread-1",
        data_mode=DataMode.DEMO,
        product_profile=product,
    )


class ParallelProductAgent(ProductMarketAgent):
    def __init__(self, barrier: Barrier) -> None:
        super().__init__()
        self.barrier = barrier

    def run(self, context):  # type: ignore[no-untyped-def]
        self.barrier.wait(timeout=2)
        return ProductMarketAnalysis(status=AgentStatus.SUCCEEDED, data_origin=DataOrigin.DEMO)


class ParallelInsightAgent(UserInsightAgent):
    def __init__(self, barrier: Barrier) -> None:
        super().__init__()
        self.barrier = barrier

    def run(self, context):  # type: ignore[no-untyped-def]
        self.barrier.wait(timeout=2)
        return UserInsight(status=AgentStatus.SUCCEEDED, data_origin=DataOrigin.DEMO)


class CountingOperationsAgent(OperationsDecisionAgent):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def run(self, context):  # type: ignore[no-untyped-def]
        self.calls += 1
        return OperationPlan(status=AgentStatus.SUCCEEDED, data_origin=DataOrigin.DEMO)


class RejectingAuditAgent(EvidenceAuditAgent):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def run(self, context):  # type: ignore[no-untyped-def]
        self.calls += 1
        return AuditResult(status=AuditStatus.REJECTED, data_origin=DataOrigin.DEMO)


class RecordingStatisticsProvider:
    def __init__(self) -> None:
        self.calls = 0

    def get_statistics(self, *, product: ProductProfile) -> StatisticsResult:
        self.calls += 1
        return StatisticsResult(
            product_id=product.product_id,
            status=AgentStatus.INSUFFICIENT_EVIDENCE,
            data_origin=DataOrigin.DEMO,
        )


def test_state_graph_runs_first_two_agents_in_parallel() -> None:
    barrier = Barrier(2)
    statistics = RecordingStatisticsProvider()
    workflow = TradePilotWorkflow(
        knowledge_store=InMemoryKnowledgeStore(),
        statistics_provider=statistics,
        product_market_agent=ParallelProductAgent(barrier),
        user_insight_agent=ParallelInsightAgent(barrier),
    )

    result = TradePilotState.model_validate(workflow.invoke(initial_state()))

    assert result.product_profile.name == "DEMO Portable Organizer"
    assert result.product_market_analysis is not None
    assert result.user_insight is not None
    assert result.statistics_result is not None
    assert statistics.calls == 1
    assert result.audit_result is not None
    assert result.audit_result.status is AuditStatus.PASS
    graph = workflow.compiled.get_graph()
    assert any(edge.source == "product_normalizer" and edge.target == "statistics_provider" for edge in graph.edges)
    assert any(edge.source == "statistics_provider" and edge.target == "product_market_agent" for edge in graph.edges)
    assert any(edge.source == "statistics_provider" and edge.target == "user_insight_agent" for edge in graph.edges)


def test_rejected_audit_retries_operations_once_then_stops() -> None:
    operations = CountingOperationsAgent()
    audit = RejectingAuditAgent()
    workflow = TradePilotWorkflow(
        knowledge_store=InMemoryKnowledgeStore(),
        operations_decision_agent=operations,
        evidence_audit_agent=audit,
    )

    result = TradePilotState.model_validate(workflow.invoke(initial_state()))

    assert operations.calls == 2
    assert audit.calls == 2
    assert result.retry_count == 1
    assert result.audit_result is not None
    assert result.audit_result.manual_review_required is True
    assert result.current_node == "persist_and_export"
