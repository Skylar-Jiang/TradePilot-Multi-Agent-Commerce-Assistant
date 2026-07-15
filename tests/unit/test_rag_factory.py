from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app
from app.rag.factory import create_knowledge_store
from app.rag.in_memory import InMemoryKnowledgeStore


def test_default_knowledge_store_factory_is_lightweight_memory(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("RAG_USE_CHROMA", raising=False)
    monkeypatch.setenv("RAG_USE_CHROMA", "false")
    get_settings.cache_clear()
    try:
        assert isinstance(create_knowledge_store(), InMemoryKnowledgeStore)
    finally:
        get_settings.cache_clear()


def test_app_uses_injected_knowledge_store_factory(tmp_path: Path) -> None:
    store = InMemoryKnowledgeStore()
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'factory.db'}",
        report_dir=tmp_path / "reports",
        upload_dir=tmp_path / "uploads",
        chroma_dir=tmp_path / "chroma",
    )

    with TestClient(create_app(settings, knowledge_store_factory=lambda: store)) as client:
        response = client.get("/api/v1/health")
        assert client.app.state.knowledge_store is store

    assert response.status_code == 200
