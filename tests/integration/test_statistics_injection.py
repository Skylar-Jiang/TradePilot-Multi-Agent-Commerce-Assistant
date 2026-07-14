from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.enums import AgentStatus
from app.main import create_app
from app.schemas.product import ProductProfile
from app.statistics.contracts import StatisticsResult


class RecordingStatisticsProvider:
    def __init__(self) -> None:
        self.product_ids: list[str] = []

    def get_statistics(self, *, product: ProductProfile) -> StatisticsResult:
        self.product_ids.append(product.product_id)
        return StatisticsResult(
            product_id=product.product_id,
            status=AgentStatus.INSUFFICIENT_EVIDENCE,
            data_origin=product.data_origin,
        )


def test_api_analysis_uses_injected_session_scoped_statistics_provider(tmp_path: Path) -> None:
    provider = RecordingStatisticsProvider()
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'statistics.db'}",
        report_dir=tmp_path / "reports",
        upload_dir=tmp_path / "uploads",
        chroma_dir=tmp_path / "chroma",
    )
    app = create_app(
        settings,
        statistics_provider_factory=lambda session: provider,
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/products",
            json={"name": "DEMO Product", "category": "demo", "data_mode": "demo"},
        )
        product_id = created.json()["data"]["product_id"]
        run = client.post(
            "/api/v1/analysis-runs",
            json={"product_id": product_id, "data_mode": "demo"},
        )

    assert run.status_code == 201
    assert provider.product_ids == [product_id]
    assert run.json()["data"]["state"]["statistics_result"]["product_id"] == product_id
