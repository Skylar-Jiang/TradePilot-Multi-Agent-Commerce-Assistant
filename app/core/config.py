import os
import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENVIRONMENT_NAME = re.compile(r"^[a-z0-9_-]+$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_debug: bool = False
    app_name: str = "TradePilot"
    app_version: str = "0.1.0"
    app_api_key: str | None = None

    database_url: str = "sqlite:///data/tradepilot.db"
    chroma_dir: Path = Path("data/chroma")
    chroma_persist_dir: Path = Path("data/chroma")
    chroma_product_collection: str = "product_knowledge"
    chroma_review_collection: str = "review_insight"
    upload_dir: Path = Path("data/uploads")
    report_dir: Path = Path("data/reports")

    openai_api_key: str | None = None
    openai_base_url: str | None = None
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    qwen_api_key: str | None = None
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model_fast: str | None = None
    model_analysis: str | None = None
    model_report: str | None = None
    model_vision: str | None = None
    model_temperature: float = 0.1
    model_timeout_seconds: int = 120
    model_max_retries: int = 3
    model_parse_max_retries: int = Field(default=1, ge=0, le=2)
    model_max_tokens: int = 4096

    embedding_model: str | None = None
    embedding_device: str = "cpu"
    rerank_model: str | None = None
    rerank_base_url: str | None = None
    rerank_enabled: bool = False
    rerank_required: bool = False
    rerank_policy: str = "conditional"
    rerank_product_enabled: bool = False
    rerank_review_enabled: bool = True
    rerank_min_candidates: int = 8
    rerank_max_candidates: int = 20
    rerank_timeout_seconds: int = 40
    rerank_max_retries: int = 3
    rag_fetch_k: int = 30
    rag_product_fetch_k: int = 30
    rag_review_fetch_k: int = 30
    rag_top_k: int = 8
    rag_score_threshold: float = 0.0
    rag_mmr_enabled: bool = True
    rag_mmr_lambda: float = Field(default=0.7, ge=0, le=1)
    rag_query_max_retries: int = Field(default=3, ge=1, le=5)
    rag_query_retry_delay_seconds: float = Field(default=0.1, ge=0, le=2)
    rag_max_per_source: int = 3
    rag_min_product_evidence: int = 1
    rag_min_review_evidence: int = 3
    rag_batch_size: int = 128
    rag_embedding_batch_size: int = 32
    rag_embedding_concurrency: int = 4
    rag_index_batch_size: int = 32
    rag_chunk_size: int = 2800
    rag_chunk_overlap: int = 300
    rag_use_chroma: bool = False
    rag_manifest_path: Path = Path("data/index_manifest.sqlite")
    peer_metadata_path: Path = Path("data/filtered/meta_pet_supplies_prefiltered.jsonl")
    peer_reviews_path: Path = Path("data/filtered/pet_supplies_reviews_prefiltered.jsonl")
    peer_cache_dir: Path = Path("data/demo/cache")
    peer_match_config_path: Path = Path("config/peer_matching.yaml")
    peer_max_reviews: int = 300
    run_worker_count: int = Field(default=2, ge=1, le=8)
    sse_poll_interval_seconds: float = Field(default=0.1, gt=0, le=5)
    sse_heartbeat_seconds: float = Field(default=10, gt=0, le=60)
    log_level: str = "INFO"
    default_data_mode: str = Field(default="demo")

    @property
    def real_model_configured(self) -> bool:
        provider_models = bool(
            self.deepseek_api_key
            and self.qwen_api_key
            and self.model_analysis
            and self.model_fast
            and self.model_report
        )
        legacy_single_provider = bool(self.openai_api_key and self.model_analysis)
        return provider_models or legacy_single_provider


def environment_dotenv_files() -> tuple[Path, Path]:
    """Return shared and environment-specific dotenv files without permitting path traversal."""
    environment = os.getenv("APP_ENV") or _read_dotenv_value(Path(".env"), "APP_ENV") or "development"
    normalized = environment.strip().lower()
    if not _ENVIRONMENT_NAME.fullmatch(normalized):
        raise ValueError("APP_ENV must contain only lowercase letters, digits, '_' or '-'")
    return Path(".env"), Path(f".env.{normalized}")


def _read_dotenv_value(path: Path, key: str) -> str | None:
    if not path.is_file():
        return None
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.removeprefix("export ").split("=", 1)
        if name.strip() == key:
            return value.strip().strip("'\"")
    return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(_env_file=environment_dotenv_files())
