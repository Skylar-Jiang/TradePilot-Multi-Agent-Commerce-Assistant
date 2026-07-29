from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, Field

from app.core.enums import AgentStatus, DataOrigin, ImplementationStatus
from app.schemas.common import DataGap
from app.schemas.product import ProductProfile


class StatisticsResult(BaseModel):
    """
    由统计实现提供的经过验证的数值事实。
    该数据模型用于封装与产品相关的各种统计指标、执行状态以及数据来源等信息。
    """

    # 关联的目标产品的唯一标识符
    product_id: str

    # 统计结果的唯一标识符，允许为空（例如在数据尚未持久化时可能没有ID）
    result_id: str | None = None

    # 代理处理该统计任务时的当前状态（例如：处理中、成功、失败等）
    status: AgentStatus

    # 数据的来源标识，指示这些统计数据是从哪里获取的（例如：内部数据库、外部API、爬虫等）
    data_origin: DataOrigin

    # 统计功能的实现状态，默认值为 SCAFFOLD（代表目前仅为脚手架/占位实现）
    implementation_status: ImplementationStatus = ImplementationStatus.SCAFFOLD

    # 核心的统计指标字典：键为指标名称，值为高精度的 Decimal 类型数值
    # 使用 default_factory=dict 确保每个实例都有独立的空字典，防止数据污染
    metrics: dict[str, Decimal] = Field(default_factory=dict)

    # 支持这些统计数据的证据 ID 列表（例如：原始数据记录、报告或日志引用的ID）
    evidence_ids: list[str] = Field(default_factory=list)

    # 数据缺口列表，用于记录在获取或计算统计数据时发现的缺失数据或异常情况
    data_gaps: list[DataGap] = Field(default_factory=list)


class StatisticsProvider(Protocol):
    """
    统计数据提供者的协议（接口）定义。
    基于 Python 的 typing.Protocol，任何实现了 `get_statistics` 方法的类
    在类型检查时都会被视为符合 StatisticsProvider 接口。
    """

    def get_statistics(
        self,
        *,
        product: ProductProfile,
        peer_group_id: str | None = None,
    ) -> StatisticsResult:
        """
        获取指定产品的统计数据。

        参数:
            product (ProductProfile): 需要获取统计数据的目标产品画像或详情对象。
            peer_group_id (str | None, 可选): 对照组或对标群体的 ID。如果提供，可以用于执行基准测试或横向比较。

        返回:
            StatisticsResult: 包含计算或收集完成的各项统计指标及相关元数据的对象。
        """
        ...
