import pytest

from app.core.config import Settings


def test_real_model_configured_accepts_deepseek_only_text_stack() -> None:
    settings = Settings(
        _env_file=None,
        deepseek_api_key="test-deepseek-key",
        model_analysis="deepseek-v4-flash",
        model_fast="deepseek-v4-flash",
        model_report="deepseek-v4-flash",
    )

    assert settings.real_model_configured is True


def test_deployment_allowlists_are_normalized() -> None:
    settings = Settings(
        _env_file=None,
        cors_allowed_origins=" https://tradepilot-preview.vercel.app/, http://127.0.0.1:5173 ",
        trusted_hosts=" tradepilot-staging.up.railway.app, healthcheck.railway.app ",
    )

    assert settings.cors_origins == [
        "https://tradepilot-preview.vercel.app",
        "http://127.0.0.1:5173",
    ]
    assert settings.allowed_hosts == [
        "tradepilot-staging.up.railway.app",
        "healthcheck.railway.app",
    ]


def test_deployment_allowlists_reject_unrestricted_wildcards() -> None:
    with pytest.raises(ValueError, match="CORS_ALLOWED_ORIGINS"):
        Settings(_env_file=None, cors_allowed_origins="*")

    with pytest.raises(ValueError, match="TRUSTED_HOSTS"):
        Settings(_env_file=None, trusted_hosts="*")
