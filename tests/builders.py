from app.core.enums import AgentStatus, DataMode, DataOrigin
from app.schemas.analysis import ProductMarketAnalysis, UserInsight
from app.schemas.product import ProductCreate, ProductProfile
from app.statistics.contracts import StatisticsResult


def build_demo_product(*, name: str = "DEMO Portable Organizer") -> ProductProfile:
    return ProductProfile(
        product_id="product-1",
        data_origin=DataOrigin.DEMO,
        **ProductCreate(
            name=name,
            category="demo-generic",
            data_mode=DataMode.DEMO,
        ).model_dump(),
    )


def build_scaffold_statistics(product: ProductProfile) -> StatisticsResult:
    return StatisticsResult(
        product_id=product.product_id,
        status=AgentStatus.INSUFFICIENT_EVIDENCE,
        data_origin=product.data_origin,
    )


def build_market_analysis() -> ProductMarketAnalysis:
    return ProductMarketAnalysis(status=AgentStatus.INSUFFICIENT_EVIDENCE, data_origin=DataOrigin.DEMO)


def build_user_insight() -> UserInsight:
    return UserInsight(status=AgentStatus.INSUFFICIENT_EVIDENCE, data_origin=DataOrigin.DEMO)
