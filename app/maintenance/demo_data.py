import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import DataOrigin, RunStatus
from app.db.models.core import (
    AgentOutput,
    AnalysisEvent,
    AnalysisRun,
    AnalysisRunStage,
    CompetitorOffer,
    Conversation,
    EvidenceReferenceRecord,
    KnowledgeSource,
    Message,
    Product,
    ProductFile,
    Report,
    Review,
)

RESET_CONFIRMATION = "RESET_SHARED_DEMO_DATA"


class DemoDataManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        url = make_url(settings.database_url)
        if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
            raise ValueError("Demo data management requires a file-backed SQLite database")
        self.database_path = Path(url.database).resolve()

    def plan(self) -> dict[str, Any]:
        engine = create_engine(self.settings.database_url)
        with Session(engine) as session:
            counts = {
                "analysis_runs": self._count(session, AnalysisRun),
                "reports": self._count(session, Report),
                "conversations": self._count(session, Conversation),
                "messages": self._count(session, Message),
                "product_files": self._count(session, ProductFile),
                "user_products": int(
                    session.scalar(
                        select(func.count()).select_from(Product).where(
                            Product.data_origin == DataOrigin.USER.value
                        )
                    )
                    or 0
                ),
                "active_analysis_runs": int(
                    session.scalar(
                        select(func.count()).select_from(AnalysisRun).where(
                            AnalysisRun.status.in_((RunStatus.PENDING.value, RunStatus.RUNNING.value))
                        )
                    )
                    or 0
                ),
                "upload_files": self._filesystem_entry_count(self.settings.upload_dir),
                "report_files": self._filesystem_entry_count(self.settings.report_dir),
            }
        engine.dispose()
        return {
            "dry_run": True,
            "counts": counts,
            "will_delete": [
                "all analysis runs, stages, events, agent outputs, evidence references and reports",
                "all conversations and messages",
                "all product-file records and configured upload/report directory contents",
                "products whose data_origin is user and their product-scoped offers, reviews and knowledge",
            ],
            "will_preserve": [
                "real/demo base products and their knowledge, offers and reviews",
                "Chroma, peer caches, public RAG/index files and tariff data",
                "Alembic schema, deployment configuration and the Railway Volume",
            ],
        }

    def export(self) -> Path:
        self._validate_paths()
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        destination = self.settings.demo_backup_dir.resolve() / stamp
        destination.mkdir(parents=True, exist_ok=False)
        with sqlite3.connect(self.database_path) as source, sqlite3.connect(
            destination / "database.sqlite"
        ) as target:
            source.backup(target)
        self._copy_directory(self.settings.upload_dir, destination / "uploads")
        self._copy_directory(self.settings.report_dir, destination / "reports")
        manifest = {**self.plan(), "created_at": datetime.now(UTC).isoformat()}
        (destination / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return destination

    def reset(self, *, confirm: str | None = None) -> dict[str, Any]:
        plan = self.plan()
        if confirm is None:
            return plan
        if confirm != RESET_CONFIRMATION:
            raise ValueError(f"Confirmation must exactly match {RESET_CONFIRMATION}")
        if plan["counts"]["active_analysis_runs"]:
            raise RuntimeError("Refusing reset while an active analysis exists")

        backup_dir = self.export()
        engine = create_engine(self.settings.database_url)
        with Session(engine) as session, session.begin():
            user_product_ids = list(
                session.scalars(
                    select(Product.product_id).where(Product.data_origin == DataOrigin.USER.value)
                ).all()
            )
            for model in (
                Message,
                Conversation,
                Report,
                EvidenceReferenceRecord,
                AgentOutput,
                AnalysisEvent,
                AnalysisRunStage,
                AnalysisRun,
                ProductFile,
            ):
                session.execute(delete(model))
            if user_product_ids:
                for model in (CompetitorOffer, Review, KnowledgeSource):
                    session.execute(delete(model).where(model.product_id.in_(user_product_ids)))
                session.execute(delete(Product).where(Product.product_id.in_(user_product_ids)))
        engine.dispose()
        self._clear_directory(self.settings.upload_dir)
        self._clear_directory(self.settings.report_dir)
        return {**plan, "dry_run": False, "backup_dir": str(backup_dir)}

    def _validate_paths(self) -> None:
        backup_root = self.settings.demo_backup_dir.resolve()
        for managed in (self.settings.upload_dir.resolve(), self.settings.report_dir.resolve()):
            if backup_root == managed or backup_root.is_relative_to(managed):
                raise ValueError("DEMO_BACKUP_DIR must not be inside UPLOAD_DIR or REPORT_DIR")

    @staticmethod
    def _count(session: Session, model: type[Any]) -> int:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)

    @staticmethod
    def _filesystem_entry_count(root: Path) -> int:
        return sum(1 for item in root.rglob("*") if item.is_file()) if root.is_dir() else 0

    @staticmethod
    def _copy_directory(source: Path, destination: Path) -> None:
        if source.is_dir():
            shutil.copytree(source, destination, symlinks=True)
        else:
            destination.mkdir(parents=True)

    @staticmethod
    def _clear_directory(root: Path) -> None:
        resolved_root = root.resolve()
        resolved_root.mkdir(parents=True, exist_ok=True)
        for child in resolved_root.iterdir():
            if child.is_symlink():
                child.unlink()
                continue
            if not child.resolve().is_relative_to(resolved_root):
                raise RuntimeError(f"Refusing to remove path outside configured directory: {child}")
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
