from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field

# ==========================================
# 导入应用内的各个模块依赖
# ==========================================
from app.background.contracts import BackgroundResult
from app.core.enums import DataMode, RetrievalScope
from app.schemas.analysis import AuditResult, OperationPlan, ProductMarketAnalysis, UserInsight
from app.schemas.common import AgentExecution, DataGap, utc_now
from app.schemas.evidence import EvidenceReference
from app.schemas.product import ProductProfile
from app.statistics.contracts import StatisticsResult


# ==========================================
# 状态合并函数
# ==========================================
# 该函数用于在图（Graph）或状态机工作流中，合并节点执行的状态字典。
# left: 现有的节点状态
# right: 新产生的节点状态
# 返回一个新的字典，包含了合并后的最新节点执行状态。
def merge_node_status(
    left: dict[str, AgentExecution], right: dict[str, AgentExecution]
) -> dict[str, AgentExecution]:
    return {**left, **right}


# ==========================================
# TradePilot 核心状态模型
# ==========================================
# 继承自 Pydantic 的 BaseModel。
# 作为多智能体工作流（Multi-Agent Workflow）的核心数据结构，
# 在整个运行生命周期中负责维护、传递和更新所有的上下文和中间结果。
class TradePilotState(BaseModel):
    # ------------------------------------------
    # 基础标识信息
    # ------------------------------------------
    task_id: str  # 当前任务的全局唯一标识符
    run_id: str  # 本次工作流运行实例的唯一标识符
    session_id: str  # 会话标识，用于将多次相关的运行关联到同一个用户交互会话中
    thread_id: str  # 线程标识，常用于追踪对话历史或多并发场景下的执行上下文

    # ------------------------------------------
    # 核心配置与产品基准数据
    # ------------------------------------------
    data_mode: DataMode  # 数据模式（例如测试模式、生产模式等，决定数据源的选取方式）
    product_profile: ProductProfile  # 核心产品画像，包含当前重点分析目标的基础业务信息
    retrieval_scope: RetrievalScope = RetrievalScope.EXACT_PRODUCT  # 检索范围，默认限定在确切的产品级别

    # ------------------------------------------
    # 竞品与同类组数据
    # ------------------------------------------
    peer_group_id: str | None = None  # 划分的同类产品组唯一标识（若存在）
    selected_peer_products: list[dict[str, Any]] = Field(default_factory=list)  # 经过筛选出的竞品或同类产品列表
    selected_parent_asins: list[str] = Field(default_factory=list)  # 选定的父级 ASIN（亚马逊标准标识号）列表，用于聚合子变体数据
    peer_group_statistics: StatisticsResult | None = None  # 针对当前所选同类产品组的统计分析结果

    # ------------------------------------------
    # 证据与检索数据
    # ------------------------------------------
    product_evidence: list[EvidenceReference] = Field(default_factory=list)  # 收集到的与产品直接相关的支撑证据列表
    review_evidence: list[EvidenceReference] = Field(default_factory=list)  # 收集到的与用户评论/反馈相关的支撑证据列表
    review_sample_scope: dict[str, Any] = Field(default_factory=dict)  # 定义评论采样的范围和过滤条件
    match_method: str = ""  # 记录用于匹配竞品或数据的具体算法/规则名称
    match_limitations: list[str] = Field(default_factory=list)  # 记录在匹配或分析过程中的限制条件及假设说明

    # ------------------------------------------
    # 补充分析与元数据
    # ------------------------------------------
    vision_analysis: dict[str, Any] | None = None  # 视觉（图像）相关分析的结果数据（如适用）
    peer_selection_metadata: dict[str, Any] = Field(default_factory=dict)  # 记录选择竞品过程中的元数据（如匹配度权重、过程日志等）
    workflow_metadata: dict[str, Any] = Field(default_factory=dict)  # 记录整个工作流执行期间的其他通用元数据

    # ------------------------------------------
    # 背景信息与目标约束
    # ------------------------------------------
    background_context: BackgroundResult | None = None  # 任务执行所需的背景上下文信息
    background_evidence: list[EvidenceReference] = Field(default_factory=list)  # 支撑背景上下文的证据列表
    target_market: str = ""  # 目标市场标识（例如特定国家、地区或特定人群）
    user_constraints: dict[str, Any] = Field(default_factory=dict)  # 用户在请求中自定义的限制条件或偏好设置

    # ------------------------------------------
    # 核心业务分析输出结果
    # ------------------------------------------
    product_market_analysis: ProductMarketAnalysis | None = None  # 最终输出的产品市场分析结果
    user_insight: UserInsight | None = None  # 最终输出的用户洞察结果（痛点、需求、购买动机等）
    operation_plan: OperationPlan | None = None  # 针对当前产品生成的运营策略或行动计划
    audit_result: AuditResult | None = None  # 对生成的分析结果或计划的审核/评估结论

    # ------------------------------------------
    # 其他支撑与统计数据
    # ------------------------------------------
    rag_evidence: list[EvidenceReference] = Field(default_factory=list)  # RAG（检索增强生成）流程中提取并使用的证据列表
    statistics_result: StatisticsResult | None = None  # 整体或者特定维度的额外统计分析数据
    data_gaps: list[DataGap] = Field(default_factory=list)  # 记录在数据收集和分析阶段发现的数据缺失或信息盲区

    # ------------------------------------------
    # 工作流控制与状态跟踪
    # ------------------------------------------
    errors: list[dict[str, Any]] = Field(default_factory=list)  # 记录工作流各节点执行过程中抛出或捕获的错误信息
    current_node: str = "pending"  # 指示当前工作流正在执行或等待执行的节点名称

    # 节点执行状态映射表
    # 使用 Annotated 结合自定义的 merge_node_status 归约函数。
    # 当工作流向状态对象更新该字段时，会自动执行合并操作，而不是直接覆盖。
    node_status: Annotated[dict[str, AgentExecution], merge_node_status] = Field(default_factory=dict)

    retry_count: int = Field(default=0, ge=0, le=1)  # 记录错误重试的次数（通过参数限制最大重试1次）

    # ------------------------------------------
    # 报告生成与时间戳
    # ------------------------------------------
    report_version: int = 0  # 生成输出报告的版本号，用于报告迭代更新
    report_id: str | None = None  # 最终生成的报告的唯一标识符
    report_paths: dict[str, str] = Field(default_factory=dict)  # 映射各种格式报告（如 PDF、Markdown 等）在存储系统中的路径
    created_at: datetime = Field(default_factory=utc_now)  # 当前状态对象创建的时间戳（默认为当前 UTC 时间）
    updated_at: datetime = Field(default_factory=utc_now)  # 当前状态对象最后一次发生更新的时间戳（默认为当前 UTC 时间）
