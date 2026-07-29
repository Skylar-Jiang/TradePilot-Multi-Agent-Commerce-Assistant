# 导入 Pydantic 的 BaseModel 和 Field，用于构建数据模型和进行数据验证
from pydantic import BaseModel, Field

# 导入系统其他模块中定义的契约（数据结构）和模式（Schemas），以便在当前文件中复用
# BackgroundResult 包含后台任务处理的结果或背景上下文
from app.background.contracts import BackgroundResult
# 引入核心业务分析和规划的数据结构：运营计划、产品市场分析、用户洞察
from app.schemas.analysis import OperationPlan, ProductMarketAnalysis, UserInsight
# 引入证据引用的数据结构，通常用于支撑分析或决策的依据
from app.schemas.evidence import EvidenceReference
# 引入产品画像（包含产品的核心信息、属性等）
from app.schemas.product import ProductProfile
# 引入统计分析结果的数据结构
from app.statistics.contracts import StatisticsResult


# 产品市场分析智能体（ProductMarketAgent）的输入模型定义
# 用于接收执行产品市场分析时所需的各种上下文、统计数据和用户约束等信息
class ProductMarketAgentInput(BaseModel):
    # 当前分析的目标产品画像
    product: ProductProfile
    # 支撑分析的证据列表，默认为空列表
    evidence: list[EvidenceReference] = Field(default_factory=list)
    # 产品的相关统计数据结果（如销售数据、流量数据等）
    statistics: StatisticsResult
    # 竞品组 ID（可选），用于定位特定的同类/竞争产品群体
    peer_group_id: str | None = None
    # 选定的父级 ASIN（亚马逊标准标识号）列表，用于聚合和对比分析，默认为空
    selected_parent_asins: list[str] = Field(default_factory=list)
    # 选定的具体竞品列表，每个竞品以字典形式存储相关属性，默认为空
    selected_peer_products: list[dict[str, object]] = Field(default_factory=list)
    # 用户的特定约束条件（如预算限制、时间要求等），默认为空字典
    user_constraints: dict[str, object] = Field(default_factory=dict)
    # 用户的原始输入数据，用于追溯或处理特殊需求，默认为空字典
    original_user_input: dict[str, object] = Field(default_factory=dict)
    # 背景上下文信息（如行业报告、历史背景等，可选）
    background_context: BackgroundResult | None = None


# 用户洞察智能体（UserInsightAgent）的输入模型定义
# 用于接收执行用户行为、需求及反馈分析时所需的上下文信息
class UserInsightAgentInput(BaseModel):
    # 当前分析的目标产品画像
    product: ProductProfile
    # 支撑洞察的证据列表（如用户评价、反馈截图等），默认为空
    evidence: list[EvidenceReference] = Field(default_factory=list)
    # 相关的统计数据结果（如用户转化率、留存率等）
    statistics: StatisticsResult
    # 竞品组 ID（可选），用于横向对比不同产品的用户反馈
    peer_group_id: str | None = None
    # 选定的父级 ASIN 列表，默认为空
    selected_parent_asins: list[str] = Field(default_factory=list)
    # 选定的具体竞品列表，默认为空
    selected_peer_products: list[dict[str, object]] = Field(default_factory=list)
    # 用户的特定约束条件（如只关注某类客群的反馈），默认为空字典
    user_constraints: dict[str, object] = Field(default_factory=dict)
    # 用户的原始输入数据，默认为空字典
    original_user_input: dict[str, object] = Field(default_factory=dict)


# 运营决策智能体（OperationsDecisionAgent）的输入模型定义
# 综合产品市场分析、用户洞察等前置结果，用于生成最终的运营计划或决策
class OperationsDecisionAgentInput(BaseModel):
    # 目标产品画像
    product: ProductProfile
    # 来自产品市场分析智能体（ProductMarketAgent）的分析结果
    product_market_analysis: ProductMarketAnalysis
    # 来自用户洞察智能体（UserInsightAgent）的分析结果
    user_insight: UserInsight
    # 相关的统计数据结果（可选）
    statistics: StatisticsResult | None = None
    # 支撑决策的证据列表，默认为空
    evidence: list[EvidenceReference] = Field(default_factory=list)
    # 竞品组 ID（可选）
    peer_group_id: str | None = None
    # 选定的父级 ASIN 列表，默认为空
    selected_parent_asins: list[str] = Field(default_factory=list)
    # 用户的特定约束条件（如利润率要求、库存限制等），默认为空字典
    user_constraints: dict[str, object] = Field(default_factory=dict)
    # 背景上下文信息（可选）
    background_context: BackgroundResult | None = None


# 证据审计智能体（EvidenceAuditAgent）的输入模型定义
# 用于对生成的运营计划进行审计，确保计划中的策略或结论有充分的证据支撑
class EvidenceAuditAgentInput(BaseModel):
    # 目标产品画像
    product: ProductProfile
    # 待审计的运营计划（由 OperationsDecisionAgent 生成）
    operation_plan: OperationPlan
    # 用于审计校验的证据列表，默认为空
    evidence: list[EvidenceReference] = Field(default_factory=list)
    # 相关的统计数据结果（可选）
    statistics: StatisticsResult | None = None
    # 竞品组 ID（可选）
    peer_group_id: str | None = None
    # 背景上下文信息（可选）
    background_context: BackgroundResult | None = None
