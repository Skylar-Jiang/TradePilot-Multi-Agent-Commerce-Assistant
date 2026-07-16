import logging
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'request-log.db'}",
        report_dir=tmp_path / "reports",
        upload_dir=tmp_path / "uploads",
        chroma_dir=tmp_path / "chroma",
    )
    return TestClient(create_app(settings))


def test_http_request_log_contains_safe_structured_fields(tmp_path: Path, caplog) -> None:  # type: ignore[no-untyped-def]
    caplog.set_level(logging.INFO, logger="tradepilot.http")

    with make_client(tmp_path) as client:
        response = client.get(
            "/api/v1/health?token=must-not-be-logged",
            headers={"X-Request-ID": "request-log-fixture", "Authorization": "Bearer secret-value"},
        )

    assert response.status_code == 200
    record = next(record for record in caplog.records if record.name == "tradepilot.http")
    assert record.event == "http_request_completed"
    assert record.request_id == "request-log-fixture"
    assert record.method == "GET"
    assert record.path == "/api/v1/health"
    assert record.status_code == 200
    assert record.duration_ms >= 0
    serialized = str(record.__dict__)
    assert "must-not-be-logged" not in serialized
    assert "secret-value" not in serialized


def test_http_request_log_records_handled_error_status(tmp_path: Path, caplog) -> None:  # type: ignore[no-untyped-def]
    caplog.set_level(logging.INFO, logger="tradepilot.http")

    with make_client(tmp_path) as client:
        response = client.get("/api/v1/products/missing-product")

    assert response.status_code == 404
    record = next(record for record in caplog.records if record.name == "tradepilot.http")
    assert record.event == "http_request_completed"
    assert record.status_code == 404
    assert record.error_type is None
