import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.rag.factory import create_knowledge_store  # noqa: E402
from app.services.knowledge_service import KnowledgeService  # noqa: E402


def main() -> None:
    with SessionLocal() as session:
        count = KnowledgeService(session, create_knowledge_store()).rebuild()
    print(f"TradePilot lightweight RAG rebuilt: documents={count}")


if __name__ == "__main__":
    main()
