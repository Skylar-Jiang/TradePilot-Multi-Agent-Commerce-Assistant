from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app

ACCESS_CODE = "test-shared-access-code"


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "database_url": f"sqlite:///{tmp_path / 'access.db'}",
        "upload_dir": tmp_path / "uploads",
        "report_dir": tmp_path / "reports",
        "chroma_dir": tmp_path / "chroma",
        "chroma_persist_dir": tmp_path / "chroma",
        "app_api_key": ACCESS_CODE,
    }
    values.update(overrides)
    return Settings(**values)


def test_core_api_requires_valid_bearer_access_code(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        missing = client.get("/api/v1/workflow/metadata")
        wrong = client.get(
            "/api/v1/workflow/metadata",
            headers={"Authorization": "Bearer wrong-code"},
        )
        accepted = client.get(
            "/api/v1/workflow/metadata",
            headers={"Authorization": f"Bearer {ACCESS_CODE}"},
        )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert ACCESS_CODE not in missing.text
    assert ACCESS_CODE not in wrong.text
    assert accepted.status_code == 200


def test_health_remains_anonymous(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


def test_cors_preflight_allows_authorization_header_without_authenticating(tmp_path: Path) -> None:
    settings = _settings(tmp_path, cors_allowed_origins="https://preview.example")
    with TestClient(create_app(settings)) as client:
        response = client.options(
            "/api/v1/workflow/metadata",
            headers={
                "Origin": "https://preview.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://preview.example"
    assert "Authorization" in response.headers["access-control-allow-headers"]


def test_staging_requires_access_code() -> None:
    with pytest.raises(ValidationError, match="APP_API_KEY is required"):
        Settings(_env_file=None, app_env="staging", app_api_key=None)


def test_staging_disables_interactive_api_documentation(tmp_path: Path) -> None:
    settings = _settings(tmp_path, app_env="staging")
    with TestClient(create_app(settings)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_development_openapi_marks_every_business_operation_as_bearer_protected(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        schema = client.get("/openapi.json").json()

    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    for path, operations in schema["paths"].items():
        for operation in operations.values():
            if path == "/api/v1/health":
                assert "security" not in operation
            else:
                assert {"HTTPBearer": []} in operation["security"]
