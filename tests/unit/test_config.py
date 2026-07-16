import sys
import tomllib
from pathlib import Path

import pytest

from app.core.config import Settings, environment_dotenv_files, get_settings


def test_project_requires_python_312() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert sys.version_info[:2] == (3, 12)
    assert project["requires-python"] == ">=3.12,<3.13"
    assert Path(".python-version").read_text(encoding="utf-8").strip() == "3.12"


def test_settings_load_without_dotenv(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'tradepilot.db'}",
        chroma_dir=tmp_path / "chroma",
        upload_dir=tmp_path / "uploads",
        report_dir=tmp_path / "reports",
    )

    assert settings.app_name == "TradePilot"
    assert settings.app_env == "development"
    assert settings.openai_api_key is None
    assert settings.database_url.startswith("sqlite:///")


def test_get_settings_loads_environment_specific_override(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / ".env").write_text(
        "APP_ENV=production\nDATABASE_URL=sqlite:///shared.db\nLOG_LEVEL=INFO\n",
        encoding="utf-8",
    )
    (tmp_path / ".env.production").write_text(
        "DATABASE_URL=sqlite:///production.db\nLOG_LEVEL=WARNING\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("APP_ENV", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_env == "production"
    assert settings.database_url == "sqlite:///production.db"
    assert settings.log_level == "WARNING"
    assert environment_dotenv_files() == (Path(".env"), Path(".env.production"))
    get_settings.cache_clear()


def test_environment_name_rejects_path_traversal(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("APP_ENV", "../production")

    with pytest.raises(ValueError, match="APP_ENV"):
        environment_dotenv_files()
