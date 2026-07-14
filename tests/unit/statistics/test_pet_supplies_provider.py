from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.enums import AgentStatus, DataMode, DataOrigin
from app.db.base import Base
from app.db.models.core import CompetitorOffer, KnowledgeSource, Product
from app.schemas.product import ProductCreate, ProductProfile
from app.statistics.providers.pet_supplies import PetSuppliesStatisticsProvider


def test_pet_supplies_provider_returns_sql_backed_metrics() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            Product(
                product_id="pet-product-1",
                name="Reflective Dog Harness",
                category="Harnesses",
                data_mode="real",
                data_origin="real",
                attributes_json={"parent_asin": "PARENT-1"},
                metadata_json={"source_file": "data/filtered/meta_pet_supplies_prefiltered.jsonl"},
                payload_json={},
            )
        )
        session.add(
            CompetitorOffer(
                offer_id="offer-1",
                product_id="pet-product-1",
                data_origin="real",
                attributes_json={"price": "24.95", "average_rating": "4.4", "rating_number": 166},
            )
        )
        session.add(
            KnowledgeSource(
                source_id="knowledge-1",
                product_id="pet-product-1",
                knowledge_type="product_knowledge",
                content="Title: Reflective Dog Harness",
                data_origin="real",
                metadata_json={"source_name": "Reflective Dog Harness"},
            )
        )
        session.commit()

        product = ProductProfile(
            product_id="pet-product-1",
            data_origin=DataOrigin.REAL,
            **ProductCreate(
                name="Reflective Dog Harness",
                category="Harnesses",
                data_mode=DataMode.REAL,
            ).model_dump(),
        )

        result = PetSuppliesStatisticsProvider(session).get_statistics(product=product)

        assert result.status is AgentStatus.SUCCEEDED
        assert result.product_id == "pet-product-1"
        assert result.data_origin is DataOrigin.REAL
        assert result.metrics["offer_count"] == Decimal("1")
        assert result.metrics["priced_offer_count"] == Decimal("1")
        assert result.metrics["avg_price"] == Decimal("24.95")
        assert result.metrics["min_price"] == Decimal("24.95")
        assert result.metrics["max_price"] == Decimal("24.95")
        assert result.metrics["avg_rating"] == Decimal("4.4")
        assert result.metrics["total_rating_count"] == Decimal("166")
        assert result.evidence_ids == ["knowledge-1"]
