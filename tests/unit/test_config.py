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
