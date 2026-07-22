from pathlib import Path

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import DataOrigin, RunStatus
from app.db.migrations import upgrade_database
from app.db.models.core import (
    AgentOutput,
    AnalysisEvent,
    AnalysisRun,
    AnalysisRunStage,
    Conversation,
    EvidenceReferenceRecord,
    KnowledgeSource,
    Message,
    Product,
    ProductFile,
    Report,
)
from app.maintenance.demo_data import RESET_CONFIRMATION, DemoDataManager


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'demo-data.db'}",
        upload_dir=tmp_path / "uploads",
        report_dir=tmp_path / "reports",
        chroma_dir=tmp_path / "chroma",
        chroma_persist_dir=tmp_path / "chroma",
        demo_backup_dir=tmp_path / "backups",
    )


def _seed_runtime_data(settings: Settings) -> None:
    upgrade_database(settings.database_url)
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        base_product = Product(
            name="Preserved base product",
            category="base",
            data_mode="real",
            data_origin=DataOrigin.REAL.value,
            payload_json={"name": "Preserved base product", "category": "base", "data_mode": "real"},
        )
        user_product = Product(
            name="Temporary shared product",
            category="demo",
            data_mode="demo",
            data_origin=DataOrigin.USER.value,
            payload_json={"name": "Temporary shared product", "category": "demo", "data_mode": "demo"},
        )
        session.add_all([base_product, user_product])
        session.flush()
        session.add_all(
            [
                KnowledgeSource(
                    product_id=base_product.product_id,
                    knowledge_type="product_knowledge",
                    content="preserve",
                    data_origin=DataOrigin.REAL.value,
                ),
                KnowledgeSource(
                    product_id=user_product.product_id,
                    knowledge_type="product_knowledge",
                    content="remove",
                    data_origin=DataOrigin.USER.value,
                ),
                ProductFile(
                    product_id=user_product.product_id,
                    file_type="document",
                    file_path=str(settings.upload_dir / "temporary.txt"),
                ),
            ]
        )
        run = AnalysisRun(
            product_id=user_product.product_id,
            data_mode="demo",
            status=RunStatus.SUCCEEDED.value,
            current_node="complete",
        )
        session.add(run)
        session.flush()
        session.add_all(
            [
                AnalysisRunStage(run_id=run.run_id, stage_key="test", sequence=0, status="succeeded"),
                AnalysisEvent(run_id=run.run_id, event_type="test"),
                AgentOutput(run_id=run.run_id, agent_name="test", status="succeeded"),
                EvidenceReferenceRecord(
                    evidence_id="test-evidence",
                    run_id=run.run_id,
                    knowledge_type="product_knowledge",
                    data_origin="user",
                    is_demo=True,
                ),
                Report(
                    run_id=run.run_id,
                    format="json+markdown",
                    file_path=str(settings.report_dir / "temporary.json"),
                    is_demo=True,
                ),
            ]
        )
        conversation = Conversation(product_id=user_product.product_id)
        session.add(conversation)
        session.flush()
        session.add(Message(conversation_id=conversation.conversation_id, role="user", content="temporary"))
        session.commit()
    engine.dispose()

    settings.upload_dir.mkdir(parents=True)
    settings.report_dir.mkdir(parents=True)
    settings.chroma_persist_dir.mkdir(parents=True)
    (settings.upload_dir / "temporary.txt").write_text("upload", encoding="utf-8")
    (settings.report_dir / "temporary.json").write_text("{}", encoding="utf-8")
    (settings.chroma_persist_dir / "preserve.index").write_text("index", encoding="utf-8")


def test_reset_defaults_to_dry_run_without_mutating_data(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _seed_runtime_data(settings)

    result = DemoDataManager(settings).reset()

    assert result["dry_run"] is True
    assert result["counts"]["analysis_runs"] == 1
    assert result["counts"]["user_products"] == 1
    assert (settings.upload_dir / "temporary.txt").is_file()
    assert not settings.demo_backup_dir.exists()


def test_confirmed_reset_backs_up_then_preserves_base_data_schema_and_indexes(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _seed_runtime_data(settings)

    result = DemoDataManager(settings).reset(confirm=RESET_CONFIRMATION)

    assert result["dry_run"] is False
    backup_dir = Path(result["backup_dir"])
    assert (backup_dir / "database.sqlite").is_file()
    assert (backup_dir / "uploads" / "temporary.txt").is_file()
    assert (backup_dir / "reports" / "temporary.json").is_file()
    assert (backup_dir / "manifest.json").is_file()
    assert list(settings.upload_dir.iterdir()) == []
    assert list(settings.report_dir.iterdir()) == []
    assert (settings.chroma_persist_dir / "preserve.index").read_text(encoding="utf-8") == "index"

    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(AnalysisRun)) == 0
        assert session.scalar(select(func.count()).select_from(Conversation)) == 0
        assert session.scalar(select(func.count()).select_from(ProductFile)) == 0
        products = session.scalars(select(Product)).all()
        knowledge = session.scalars(select(KnowledgeSource)).all()
        assert [(item.name, item.data_origin) for item in products] == [
            ("Preserved base product", DataOrigin.REAL.value)
        ]
        assert [item.content for item in knowledge] == ["preserve"]
        assert "alembic_version" in inspect(engine).get_table_names()
    engine.dispose()


def test_confirmed_reset_refuses_while_an_analysis_is_active(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _seed_runtime_data(settings)
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        run = session.scalar(select(AnalysisRun))
        assert run is not None
        run.status = RunStatus.RUNNING.value
        session.commit()
    engine.dispose()

    try:
        DemoDataManager(settings).reset(confirm=RESET_CONFIRMATION)
    except RuntimeError as exc:
        assert "active analysis" in str(exc).lower()
    else:
        raise AssertionError("active analysis reset should have been refused")

    assert (settings.upload_dir / "temporary.txt").is_file()
    assert not settings.demo_backup_dir.exists()
