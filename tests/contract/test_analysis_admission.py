from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "database_url": f"sqlite:///{tmp_path / 'admission.db'}",
        "upload_dir": tmp_path / "uploads",
        "report_dir": tmp_path / "reports",
        "chroma_dir": tmp_path / "chroma",
        "chroma_persist_dir": tmp_path / "chroma",
        "run_worker_count": 1,
    }
    values.update(overrides)
    return Settings(**values)


def _product(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/products",
        json={"name": name, "category": "demo", "data_mode": "demo"},
    )
    assert response.status_code == 201
    return response.json()["data"]["product_id"]


def _start(client: TestClient, product_id: str):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/analysis-runs",
        json={"product_id": product_id, "data_mode": "demo"},
    )


def test_duplicate_active_product_run_is_rejected(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("app.services.run_dispatcher.RunDispatcher.submit", lambda self, run_id: None)
    with TestClient(create_app(_settings(tmp_path))) as client:
        product_id = _product(client, "Duplicate guard")
        first = _start(client, product_id)
        duplicate = _start(client, product_id)

    assert first.status_code == 202
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "analysis_already_running"


def test_global_active_run_limit_is_enforced(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("app.services.run_dispatcher.RunDispatcher.submit", lambda self, run_id: None)
    with TestClient(create_app(_settings(tmp_path, analysis_max_active_runs=1))) as client:
        first_product = _product(client, "First active")
        second_product = _product(client, "Second active")
        first = _start(client, first_product)
        at_capacity = _start(client, second_product)

    assert first.status_code == 202
    assert at_capacity.status_code == 429
    assert at_capacity.json()["error"]["code"] == "analysis_capacity_reached"


def test_accepted_analysis_starts_are_rate_limited(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("app.services.run_dispatcher.RunDispatcher.submit", lambda self, run_id: None)
    settings = _settings(
        tmp_path,
        analysis_max_active_runs=8,
        analysis_rate_limit_requests=2,
        analysis_rate_limit_window_seconds=60,
    )
    with TestClient(create_app(settings)) as client:
        products = [_product(client, f"Rate product {index}") for index in range(3)]
        responses = [_start(client, product_id) for product_id in products]

    assert [response.status_code for response in responses] == [202, 202, 429]
    assert responses[-1].json()["error"]["code"] == "analysis_rate_limited"
