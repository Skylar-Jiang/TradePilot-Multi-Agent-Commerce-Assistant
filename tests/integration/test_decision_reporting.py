import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adapters.demo import DemoDomainAdapter
from app.core.config import Settings
from app.core.enums import AuditStatus, DataMode
from app.db.base import Base
from app.db.repositories.sqlalchemy import SqlAlchemyProductRepository
from app.rag.in_memory import InMemoryKnowledgeStore
from app.schemas.analysis import AnalysisRunCreate
from app.services.analysis_service import AnalysisService


def test_demo_workflow_exports_audited_content_playbook(tmp_path: Path) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        store = InMemoryKnowledgeStore()
        product = DemoDomainAdapter().seed(
            session,
            SqlAlchemyProductRepository(session),
            store,
        )
        service = AnalysisService(
            session=session,
            knowledge_store=store,
            report_dir=tmp_path,
            settings=Settings(_env_file=None, database_url="sqlite://"),
        )

        run = service.start(
            AnalysisRunCreate(product_id=product.product_id, data_mode=DataMode.DEMO)
        )
        assert run.report_id is not None
        report = service.get_report(run.report_id)

        payload = json.loads(Path(report.json_path).read_text(encoding="utf-8"))
        markdown = Path(report.markdown_path).read_text(encoding="utf-8")
        content = payload["sections"]["content_playbook"]

        assert report.audit_status is AuditStatus.PASS
        assert run.state["report_version"] == 1
        assert content["title"]
        assert len(content["bullets"]) == 5
        assert set(content["customer_service"]) == {
            "compatibility",
            "issue",
            "returns",
            "shipping",
        }
        assert payload["sections"]["audit_result"]["issues"] == []
        assert "## Content playbook" in markdown
        assert "## Evidence audit" in markdown
        assert "## Data limitations" in markdown
