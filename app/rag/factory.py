from collections.abc import Callable

from app.rag.contracts import KnowledgeStore
from app.rag.in_memory import InMemoryKnowledgeStore

KnowledgeStoreFactory = Callable[[], KnowledgeStore]


def create_knowledge_store() -> KnowledgeStore:
    """Default Demo/Test store; inject another factory to select Chroma later."""

    return InMemoryKnowledgeStore()
