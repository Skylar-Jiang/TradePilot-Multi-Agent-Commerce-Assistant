from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import (
    AgentStatus,
    AuditStatus,
    DataMode,
    DataOrigin,
    ImplementationStatus,
    RunStageStatus,
    RunStatus,
)
from app.schemas.common import Conclusion, DataGap


# ==========================================
# 基础智能体输出模型 (ScaffoldAgentOutput)
# ==========================================
# 该类作为各个具体分析智能体输出结果的基类，定义了通用的字段。
# 包括状态、数据来源、实现状态以及各种执行过程中的元数据（如证据、警告、错误、模型调用次数、Token 消耗等）。
class ScaffoldAgentOutput(BaseModel):
    status: AgentStatus
    data_origin: DataOrigin
    implementation_status: ImplementationStatus = ImplementationStatus.SCAFFOLD
    conclusions: list[Conclusion] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    data_gaps: list[DataGap] = Field(default_factory=list)
    evidence_references: list[dict[str, Any]] = Field(default_factory=list)
    missing_evidence_types: list[str] = Field(default_factory=list)
    unverifiable_claims: list[str] = Field(default_factory=list)
    statistics_result_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    model_call_count: int = Field(default=0, ge=0)
    parse_retry_count: int = Field(default=0, ge=0)
    token_usage: dict[str, int] | None = None
    structured_output_parser: str | None = None
    scaffold_note: str = "Deterministic scaffold output; deferred business analysis is not implemented."


# ==========================================
# 产品市场分析模型 (ProductMarketAnalysis)
# ==========================================
# 继承自 ScaffoldAgentOutput，用于存储产品在市场层面的分析结果。
# 包含产品总结、价格分析、竞品特征基线、结构与场景、品牌定位、评价分析、
# 同质化风险、差异化机会、预发布验证、优劣势以及优化建议等详细的市场指标。
class ProductMarketAnalysis(ScaffoldAgentOutput):
    peer_group_id: str | None = None
    selected_parent_asins: list[str] = Field(default_factory=list)
    product_summary: str = ""
    price_analysis: str = ""
    feature_baseline: list[str] = Field(default_factory=list)
    structure_and_scenarios: list[str] = Field(default_factory=list)
    brand_positioning: list[str] = Field(default_factory=list)
    rating_analysis: str = ""
    homogenization_risks: list[str] = Field(default_factory=list)
    differentiation_opportunities: list[str] = Field(default_factory=list)
    missing_parameters: list[str] = Field(default_factory=list)
    prelaunch_validations: list[str] = Field(default_factory=list)
    reasoned_hypotheses: list[str] = Field(default_factory=list)
    product_category: str = ""
    product_functions: list[str] = Field(default_factory=list)
    key_parameters: list[str] = Field(default_factory=list)
    usage_scenarios: list[str] = Field(default_factory=list)
    target_users: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    competitor_differences: list[str] = Field(default_factory=list)
    target_market_fit: str | None = None
    optimization_suggestions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


# ==========================================
# 用户洞察分析模型 (UserInsight)
# ==========================================
# 继承自 ScaffoldAgentOutput，专注于用户需求、评价和行为的深度分析。
# 包括用户的共同需求、正面体验、痛点、购买决策因素、特征使用及维护担忧、
# 目标用户画像、高频关键词以及针对产品的改进建议等。
class UserInsight(ScaffoldAgentOutput):
    peer_group_id: str | None = None
    selected_parent_asins: list[str] = Field(default_factory=list)
    insight_summary: str = ""
    common_needs: list[str] = Field(default_factory=list)
    positive_experiences: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    purchase_factors: list[str] = Field(default_factory=list)
    feature_usage_maintenance_concerns: list[str] = Field(default_factory=list)
    prelaunch_validations: list[str] = Field(default_factory=list)
    convertible_selling_points: list[str] = Field(default_factory=list)
    optimization_directions: list[str] = Field(default_factory=list)
    sample_limitations: list[str] = Field(default_factory=list)
    reasoned_hypotheses: list[str] = Field(default_factory=list)
    target_user_profiles: list[str] = Field(default_factory=list)
    identity_or_demographic_observations: list[str] = Field(default_factory=list)
    usage_scenarios: list[str] = Field(default_factory=list)
    purchase_motivations: list[str] = Field(default_factory=list)
    positive_concerns: list[str] = Field(default_factory=list)
    frequent_keywords: list[str] = Field(default_factory=list)
    negative_review_reasons: list[str] = Field(default_factory=list)
    user_expectations: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)


# ==========================================
# 运营计划模型 (OperationPlan)
# ==========================================
# 继承自 ScaffoldAgentOutput，用于生成产品的市场推广和运营执行策略。
# 包括产品定位、营销目标、目标客群、价值主张、定价与渠道策略、
# 消息传递策略、具体的上市行动步骤以及下一步计划。
class OperationPlan(ScaffoldAgentOutput):
    positioning: str = ""
    marketing_objective: str = ""
    target_segments: list[str] = Field(default_factory=list)
    value_propositions: list[str] = Field(default_factory=list)
    pricing_strategy: list[str] = Field(default_factory=list)
    channel_strategy: list[str] = Field(default_factory=list)
    messaging_strategy: list[str] = Field(default_factory=list)
    launch_actions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    peer_group_id: str | None = None
    selected_parent_asins: list[str] = Field(default_factory=list)
    analysis_scopes: dict[str, Any] = Field(default_factory=dict)


# ==========================================
# 审计结果模型 (AuditResult)
# ==========================================
# 用于记录系统对数据或流程的审计验证结果。
# 包含发现的具体问题、证据冲突点、未解决的疑问、模型与 Token 统计，
# 以及是否需要人工介入复核（manual_review_required）等标识。
class AuditResult(BaseModel):
    status: AuditStatus
    data_origin: DataOrigin
    implementation_status: ImplementationStatus = ImplementationStatus.SCAFFOLD
    issues: list[str] = Field(default_factory=list)
    conflicting_evidence_ids: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    manual_review_required: bool = False
    model_call_count: int = Field(default=0, ge=0)
    parse_retry_count: int = Field(default=0, ge=0)
    token_usage: dict[str, int] | None = None
    structured_output_parser: str | None = None


# ==========================================
# 分析任务创建模型 (AnalysisRunCreate)
# ==========================================
# 用户或系统发起新分析任务时的输入数据验证模型。
# 包含目标产品 ID、数据模式、会话与线程 ID、目标市场、生效日期、
# 查询日期以及用户自定义的约束条件等参数。
class AnalysisRunCreate(BaseModel):
    product_id: str
    data_mode: DataMode = DataMode.DEMO
    session_id: str | None = None
    thread_id: str | None = None
    target_market: str | None = None
    jurisdiction: str = ""
    platform: str = ""
    background_context_types: list[str] = Field(default_factory=list)
    background_provider: str | None = None
    effective_date: date | None = None
    query_date: date | None = None
    user_constraints: dict[str, Any] = Field(default_factory=dict)


# ==========================================
# 分析任务读取模型 (AnalysisRunRead)
# ==========================================
# 用于向客户端返回正在执行或已完成的整体分析任务状态。
# 包含任务 ID、关联产品、当前运行状态、当前所处节点名称、重试次数以及任务内部字典状态。
class AnalysisRunRead(BaseModel):
    run_id: str
    product_id: str
    data_mode: DataMode
    status: RunStatus
    current_node: str
    retry_count: int
    report_id: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)


# ==========================================
# 反馈创建模型 (FeedbackCreate)
# ==========================================
# 用于接收用户对特定分析结果的主观反馈或修正意见。
class FeedbackCreate(BaseModel):
    message: str = Field(min_length=1)


# ==========================================
# 智能体输出读取模型 (AgentOutputRead)
# ==========================================
# 用于查询单个特定智能体（Agent）的执行记录详情。
# 包含智能体名称、最终状态、输入与输出的数据结构、可能发生的错误对象以及详细的执行时间统计。
class AgentOutputRead(BaseModel):
    agent_name: str
    status: AgentStatus
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None


# ==========================================
# 任务阶段读取模型 (RunStageRead)
# ==========================================
# 用于描述整个工作流（Run）中某个特定阶段（Stage）的执行状态。
# 包含阶段唯一标识、执行顺序、当前状态、时间戳记录、特定负载数据及相关错误信息。
class RunStageRead(BaseModel):
    stage_key: str
    sequence: int
    status: RunStageStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None


# ==========================================
# 分析事件读取模型 (AnalysisEventRead)
# ==========================================
# 用于记录和查询系统分析过程中的细粒度事件流（Event Log）。
# 包含事件 ID、所属任务 ID、事件类型、关联阶段的 Key、具体的事件负载内容及创建时间。
class AnalysisEventRead(BaseModel):
    event_id: int
    run_id: str
    event_type: str
    stage_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
