import json
from collections.abc import Callable
from time import perf_counter

from langgraph.graph import END, START, StateGraph

from app.agents.contracts import (
    EvidenceAuditAgentInput,
    OperationsDecisionAgentInput,
    ProductMarketAgentInput,
    UserInsightAgentInput,
)
from app.agents.evidence_audit import EvidenceAuditAgent
from app.agents.operations_decision import OperationsDecisionAgent
from app.agents.product_market import ProductMarketAgent
from app.agents.user_insight import UserInsightAgent
from app.core.enums import AgentStatus, AuditStatus, KnowledgeType
from app.rag.contracts import KnowledgeStore
from app.rag.pipeline import RetrievalPipeline
from app.rag.utils import stable_id
from app.schemas.common import AgentExecution, DataGap, utc_now
from app.schemas.evidence import EvidenceReference
from app.statistics.contracts import StatisticsProvider
from app.statistics.stub import ScaffoldStatisticsProvider
from app.workflows.state import TradePilotState

# ==========================================
# 类型别名定义区
# 定义持久化回调和进度回调的函数签名
# ==========================================
PersistCallback = Callable[[TradePilotState], dict[str, object]]
ProgressCallback = Callable[[str, str, dict[str, object]], None]


# ==========================================
# 辅助函数：_merge_data_gaps
# 作用：合并多个数据缺失记录（DataGap），通过元组 (code, field, reason, required_for) 进行去重，
#       确保相同的数据缺失记录只保留一份。
# ==========================================
def _merge_data_gaps(*groups: list[DataGap]) -> list[DataGap]:
    merged: list[DataGap] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for group in groups:
        for gap in group:
            key = (gap.code, gap.field, gap.reason, gap.required_for)
            if key not in seen:
                seen.add(key)
                merged.append(gap)
    return merged


# ==========================================
# 辅助函数：_execution
# 作用：生成节点执行状态信息的字典。
#       用于记录代理（Agent）或图节点的执行状态、开始时间、结束时间和耗时等指标。
# ==========================================
def _execution(
    name: str,
    status: AgentStatus = AgentStatus.SUCCEEDED,
    *,
    started_at=None,  # type: ignore[no-untyped-def]
    completed_at=None,  # type: ignore[no-untyped-def]
    duration_ms: int | None = None,
) -> dict[str, AgentExecution]:
    return {
        name: AgentExecution(
            agent_name=name,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )
    }


# ==========================================
# 核心类：TradePilotWorkflow
# 作用：定义和封装整个多智能体工作流的生命周期管理，
#       基于 LangGraph 构建并执行各处理节点和智能体。
# ==========================================
class TradePilotWorkflow:
    def __init__(
        self,
        *,
        knowledge_store: KnowledgeStore,
        statistics_provider: StatisticsProvider | None = None,
        product_market_agent: ProductMarketAgent | None = None,
        user_insight_agent: UserInsightAgent | None = None,
        operations_decision_agent: OperationsDecisionAgent | None = None,
        evidence_audit_agent: EvidenceAuditAgent | None = None,
        persist_callback: PersistCallback | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        # 1. 知识库与数据提供者初始化
        self.knowledge_store = knowledge_store
        self.retrieval_pipeline = RetrievalPipeline(knowledge_store)
        self.statistics_provider = statistics_provider or ScaffoldStatisticsProvider()

        # 2. 智能体(Agents)初始化
        # 若外部未提供，则自动实例化默认的智能体对象
        self.product_market_agent = product_market_agent or ProductMarketAgent(
            retrieval_pipeline=self.retrieval_pipeline
        )
        self.user_insight_agent = user_insight_agent or UserInsightAgent(
            retrieval_pipeline=self.retrieval_pipeline
        )
        self.operations_decision_agent = operations_decision_agent or OperationsDecisionAgent()
        self.evidence_audit_agent = evidence_audit_agent or EvidenceAuditAgent()

        # 3. 回调函数配置
        self.persist_callback = persist_callback
        self.progress_callback = progress_callback

        # 4. 构建并编译状态图
        self.compiled = self._build_graph().compile()

    # ==========================================
    # 方法：_build_graph
    # 作用：构建并连接 LangGraph 状态图的所有节点与边。
    #       定义了整个工作流从 START 到 END 的执行路径，包括并行处理和条件路由。
    # ==========================================
    def _build_graph(self) -> StateGraph:
        graph = StateGraph(TradePilotState)

        # 添加各个处理节点，并使用 _tracked 包装以进行状态和进度追踪
        graph.add_node("input_validator", self._tracked("input_validator", self._input_validator))
        graph.add_node("product_normalizer", self._tracked("product_normalizer", self._product_normalizer))
        graph.add_node("statistics_provider", self._tracked("statistics_provider", self._statistics_provider))
        graph.add_node("product_market_agent", self._tracked("product_market_agent", self._product_market))
        graph.add_node("user_insight_agent", self._tracked("user_insight_agent", self._user_insight))
        graph.add_node(
            "operations_decision_agent",
            self._tracked("operations_decision_agent", self._operations_decision),
        )
        graph.add_node("evidence_audit_agent", self._tracked("evidence_audit_agent", self._evidence_audit))
        graph.add_node("persist_and_export", self._tracked("persist_and_export", self._persist_and_export))

        # 定义执行流（添加边）
        # START -> 验证输入 -> 产品标准化 -> 统计数据提供
        graph.add_edge(START, "input_validator")
        graph.add_edge("input_validator", "product_normalizer")
        graph.add_edge("product_normalizer", "statistics_provider")

        # 统计数据提供 -> 并行触发 "产品市场分析" 和 "用户洞察分析"
        graph.add_edge("statistics_provider", "product_market_agent")
        graph.add_edge("statistics_provider", "user_insight_agent")

        # 上述两个并行智能体执行完毕后，汇聚到 "运营决策智能体"
        graph.add_edge(
            ["product_market_agent", "user_insight_agent"],
            "operations_decision_agent",
        )

        # 运营决策 -> 证据审计
        graph.add_edge("operations_decision_agent", "evidence_audit_agent")

        # 证据审计节点通过 _route_after_audit 方法决定下一步走向：
        # - "retry": 重新执行运营决策
        # - "persist": 进入持久化和导出节点
        graph.add_conditional_edges(
            "evidence_audit_agent",
            self._route_after_audit,
            {"retry": "operations_decision_agent", "persist": "persist_and_export"},
        )

        # 持久化节点完成后到达结束状态
        graph.add_edge("persist_and_export", END)
        return graph

    # ==========================================
    # 方法：_tracked
    # 作用：高阶函数（装饰器模式），用于包装图节点方法。
    #       在节点执行的前后调用 progress_callback（如果存在），记录节点的运行、成功或失败状态。
    # ==========================================
    def _tracked(self, node_name: str, node: Callable):  # type: ignore[no-untyped-def]
        def invoke(state: TradePilotState) -> dict[str, object]:
            if self.progress_callback:
                self.progress_callback(node_name, "started", {"status": "running"})
            try:
                result = node(state)
            except Exception as exc:
                if self.progress_callback:
                    self.progress_callback(
                        node_name,
                        "failed",
                        {"status": "failed", "error_type": type(exc).__name__},
                    )
                raise
            if self.progress_callback:
                executions = result.get("node_status")
                execution = executions.get(node_name) if isinstance(executions, dict) else None
                self.progress_callback(
                    node_name,
                    "completed",
                    {
                        "status": "succeeded",
                        "duration_ms": getattr(execution, "duration_ms", None),
                    },
                )
            return result

        return invoke

    # ==========================================
    # 方法：invoke
    # 作用：工作流的入口，接收初始状态并触发图的执行。
    # ==========================================
    def invoke(self, state: TradePilotState) -> dict[str, object]:
        return self.compiled.invoke(state)

    # ==========================================
    # 节点：_input_validator
    # 作用：静态方法，用于验证传入的 TradePilotState 是否合法（Pydantic 校验）。
    # ==========================================
    @staticmethod
    def _input_validator(state: TradePilotState) -> dict[str, object]:
        TradePilotState.model_validate(state)
        return {
            "current_node": "input_validator",
            "node_status": _execution("input_validator"),
        }

    # ==========================================
    # 节点：_product_normalizer
    # 作用：标准化产品信息，并通过 RAG (检索增强生成) 管道从知识库中检索相关证据和缺失的数据缺口。
    #       将检索到的证据分类为产品证据 (PRODUCT_KNOWLEDGE) 和评论洞察 (REVIEW_INSIGHT)。
    # ==========================================
    def _product_normalizer(self, state: TradePilotState) -> dict[str, object]:
        started_at = utc_now()
        started = perf_counter()

        # 去除产品名称和分类的首尾空格
        product = state.product_profile.model_copy(
            update={"name": state.product_profile.name.strip(), "category": state.product_profile.category.strip()}
        )
        evidence = list(state.background_evidence)
        gaps = []

        # 遍历所有知识类型，从知识库中检索内容
        for knowledge_type in KnowledgeType:
            result = self.knowledge_store.retrieve(
                query=product.name,
                product_id=product.product_id,
                knowledge_type=knowledge_type,
                scope=state.retrieval_scope,
                peer_group_id=state.peer_group_id,
            )
            evidence.extend(result.evidence)
            gaps.extend(result.data_gaps)

        # 若按竞品群组检索且存在选定的父级 ASIN 列表，过滤证据以仅保留背景或属于选中竞品的证据
        if state.retrieval_scope.value == "peer_group" and state.selected_parent_asins:
            selected = set(state.selected_parent_asins)
            evidence = [
                item
                for item in evidence
                if item.metadata.get("evidence_scope") == "product_background"
                or str(item.metadata.get("parent_asin") or "") in selected
            ]

        # 证据分类处理
        product_evidence = [
            item for item in evidence if item.knowledge_type is KnowledgeType.PRODUCT_KNOWLEDGE
        ]
        review_evidence = [
            item for item in evidence if item.knowledge_type is KnowledgeType.REVIEW_INSIGHT
        ]
        completed_at = utc_now()

        return {
            "product_profile": product,
            "rag_evidence": evidence,
            "product_evidence": product_evidence,
            "review_evidence": review_evidence,
            "review_sample_scope": {
                "peer_group_id": state.peer_group_id,
                "selected_parent_asins": state.selected_parent_asins,
                "retrieved_review_evidence_count": len(review_evidence),
            },
            "data_gaps": _merge_data_gaps(state.data_gaps, gaps),
            "current_node": "product_normalizer",
            "node_status": _execution(
                "product_normalizer",
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=round((perf_counter() - started) * 1000),
            ),
        }

    # ==========================================
    # 节点：_statistics_provider
    # 作用：获取结构化的统计数据（如 SQL 分析数据），并将其转换为证据 (EvidenceReference) 的格式
    #       加入到全局证据列表中，同时合并数据缺口。
    # ==========================================
    def _statistics_provider(self, state: TradePilotState) -> dict[str, object]:
        started_at = utc_now()
        started = perf_counter()

        # 根据是否存在竞品群组ID，获取不同的统计结果
        if state.peer_group_id:
            result = self.statistics_provider.get_statistics(
                product=state.product_profile,
                peer_group_id=state.peer_group_id,
            )
        else:
            result = self.statistics_provider.get_statistics(product=state.product_profile)

        # 将统计结果封装为 EvidenceReference 对象
        statistics_evidence = EvidenceReference(
            evidence_id=stable_id(
                "statistics",
                state.product_profile.product_id,
                state.peer_group_id or "exact_product",
                json.dumps(result.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
            ),
            evidence_type="sql_statistics",
            knowledge_type=KnowledgeType.PRODUCT_KNOWLEDGE,
            source_name="TradePilot peer-group SQL statistics",
            excerpt=json.dumps(result.metrics, ensure_ascii=False, default=str, sort_keys=True),
            data_origin=result.data_origin,
            is_demo=result.data_origin.value == "demo",
            metadata={
                "source_type": "sql_statistics",
                "evidence_scope": "peer_group" if state.peer_group_id else "exact_product",
                "peer_group_id": state.peer_group_id or "",
                "candidate_product_id": state.product_profile.product_id,
            },
        )

        merged_gaps = _merge_data_gaps(state.data_gaps, result.data_gaps)
        # 更新统计结果的证据ID列表及数据缺失情况
        result = result.model_copy(
            update={
                "evidence_ids": list(dict.fromkeys([*result.evidence_ids, statistics_evidence.evidence_id])),
                "data_gaps": merged_gaps,
            }
        )
        completed_at = utc_now()

        return {
            "statistics_result": result,
            "peer_group_statistics": result if state.peer_group_id else None,
            "rag_evidence": [*state.rag_evidence, statistics_evidence],
            "product_evidence": [*state.product_evidence, statistics_evidence],
            "data_gaps": merged_gaps,
            "current_node": "statistics_provider",
            "node_status": _execution(
                "statistics_provider",
                result.status,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=round((perf_counter() - started) * 1000),
            ),
        }

    # ==========================================
    # 节点：_product_market
    # 作用：产品市场分析智能体节点。
    #       利用产品证据、统计数据、用户约束等，调用对应智能体分析市场趋势与产品定位。
    # ==========================================
    def _product_market(self, state: TradePilotState) -> dict[str, object]:
        if state.statistics_result is None:
            raise ValueError("statistics result is required")
        evidence = state.product_evidence
        started_at = utc_now()
        started = perf_counter()

        # 调用产品市场智能体
        output = self.product_market_agent.run(
            ProductMarketAgentInput(
                product=state.product_profile,
                evidence=evidence,
                statistics=state.statistics_result,
                peer_group_id=state.peer_group_id,
                selected_parent_asins=state.selected_parent_asins,
                selected_peer_products=state.selected_peer_products,
                user_constraints=state.user_constraints,
                background_context=state.background_context,
            )
        )
        completed_at = utc_now()

        return {
            "product_market_analysis": output,
            "node_status": _execution(
                "product_market_agent",
                output.status,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=round((perf_counter() - started) * 1000),
            ),
        }

    # ==========================================
    # 节点：_user_insight
    # 作用：用户洞察智能体节点。
    #       利用评论证据、统计数据等，调用对应智能体分析用户反馈、需求及痛点。
    # ==========================================
    def _user_insight(self, state: TradePilotState) -> dict[str, object]:
        if state.statistics_result is None:
            raise ValueError("statistics result is required")
        evidence = state.review_evidence
        started_at = utc_now()
        started = perf_counter()

        # 调用用户洞察智能体
        output = self.user_insight_agent.run(
            UserInsightAgentInput(
                product=state.product_profile,
                evidence=evidence,
                statistics=state.statistics_result,
                peer_group_id=state.peer_group_id,
                selected_parent_asins=state.selected_parent_asins,
                selected_peer_products=state.selected_peer_products,
                user_constraints=state.user_constraints,
            )
        )
        completed_at = utc_now()

        return {
            "user_insight": output,
            "node_status": _execution(
                "user_insight_agent",
                output.status,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=round((perf_counter() - started) * 1000),
            ),
        }

    # ==========================================
    # 节点：_operations_decision
    # 作用：运营决策智能体节点。
    #       汇总市场分析与用户洞察的结果，结合统计和证据数据，生成具体的运营计划与策略。
    # ==========================================
    def _operations_decision(self, state: TradePilotState) -> dict[str, object]:
        if state.product_market_analysis is None or state.user_insight is None:
            raise ValueError("parallel agent outputs are required")
        started_at = utc_now()
        started = perf_counter()

        # 调用运营决策智能体
        output = self.operations_decision_agent.run(
            OperationsDecisionAgentInput(
                product=state.product_profile,
                product_market_analysis=state.product_market_analysis,
                user_insight=state.user_insight,
                statistics=state.statistics_result,
                evidence=state.rag_evidence,
                peer_group_id=state.peer_group_id,
                selected_parent_asins=state.selected_parent_asins,
                user_constraints=state.user_constraints,
                background_context=state.background_context,
            )
        )
        completed_at = utc_now()

        return {
            "operation_plan": output,
            "current_node": "operations_decision_agent",
            "node_status": _execution(
                "operations_decision_agent",
                output.status,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=round((perf_counter() - started) * 1000),
            ),
        }

    # ==========================================
    # 节点：_evidence_audit
    # 作用：证据审计智能体节点。
    #       审核生成的运营计划是否具有充足的数据与事实支撑（基于 RAG 检索的证据）。
    #       如果审计拒绝，则尝试控制重试逻辑。
    # ==========================================
    def _evidence_audit(self, state: TradePilotState) -> dict[str, object]:
        if state.operation_plan is None:
            raise ValueError("operation plan is required")
        started_at = utc_now()
        started = perf_counter()

        # 调用审计智能体
        output = self.evidence_audit_agent.run(
            EvidenceAuditAgentInput(
                product=state.product_profile,
                operation_plan=state.operation_plan,
                evidence=state.rag_evidence,
                statistics=state.statistics_result,
                peer_group_id=state.peer_group_id,
                background_context=state.background_context,
            )
        )
        completed_at = utc_now()

        # 审计重试机制处理：
        # 如果被拒绝且这是第一次尝试（retry_count == 0），标记重试状态。
        # 如果再次被拒绝，则最终停止并标记需人工复核。
        if output.status is AuditStatus.REJECTED and state.retry_count == 0:
            current_node = "evidence_audit_retry"
            retry_count = 1
        elif output.status is AuditStatus.REJECTED:
            current_node = "evidence_audit_final"
            retry_count = state.retry_count
            output = output.model_copy(update={"manual_review_required": True})
        else:
            current_node = "evidence_audit_pass"
            retry_count = state.retry_count

        return {
            "audit_result": output,
            "retry_count": retry_count,
            "current_node": current_node,
            "node_status": _execution(
                "evidence_audit_agent",
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=round((perf_counter() - started) * 1000),
            ),
        }

    # ==========================================
    # 条件路由：_route_after_audit
    # 作用：基于证据审计节点产生的结果（当前节点标识）进行状态流转决策。
    #       返回 'retry' 回到运营决策节点，或 'persist' 走向结束。
    # ==========================================
    @staticmethod
    def _route_after_audit(state: TradePilotState) -> str:
        return "retry" if state.current_node == "evidence_audit_retry" else "persist"

    # ==========================================
    # 节点：_persist_and_export
    # 作用：处理工作流执行后的持久化与状态更新。
    #       收集所有指标（如总耗时、各阶段用时等），并调用外部的持久化回调保存结果。
    # ==========================================
    def _persist_and_export(self, state: TradePilotState) -> dict[str, object]:
        completed_at = utc_now()
        rag_execution = state.node_status.get("product_normalizer")
        statistics_execution = state.node_status.get("statistics_provider")

        # 收集整个工作流层面的元数据指标
        workflow_metadata = {
            **state.workflow_metadata,
            "started_at": state.created_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_ms": round((completed_at - state.created_at).total_seconds() * 1000),
            "parallel_agent_overlap": self._parallel_overlap(state),
            "rag_retrieval_duration_ms": rag_execution.duration_ms if rag_execution else None,
            "statistics_query_duration_ms": (
                statistics_execution.duration_ms if statistics_execution else None
            ),
        }

        # 构造最终状态
        final_state = state.model_copy(
            update={
                "current_node": "persist_and_export",
                "workflow_metadata": workflow_metadata,
                "updated_at": completed_at,
            }
        )

        # 触发持久化回调
        updates = self.persist_callback(final_state) if self.persist_callback else {}

        return {
            **updates,
            "current_node": "persist_and_export",
            "workflow_metadata": workflow_metadata,
            "updated_at": completed_at,
            "node_status": _execution("persist_and_export"),
        }

    # ==========================================
    # 辅助方法：_parallel_overlap
    # 作用：计算判断市场分析和用户洞察两个并行节点在执行时间上是否有重叠，
    #       用于统计和分析并发执行效率。
    # ==========================================
    @staticmethod
    def _parallel_overlap(state: TradePilotState) -> bool:
        market = state.node_status.get("product_market_agent")
        insight = state.node_status.get("user_insight_agent")
        if not market or not insight:
            return False
        if not all((market.started_at, market.completed_at, insight.started_at, insight.completed_at)):
            return False
        return max(market.started_at, insight.started_at) < min(market.completed_at, insight.completed_at)
