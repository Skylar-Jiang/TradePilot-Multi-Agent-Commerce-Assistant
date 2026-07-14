from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adapters.base import DomainAdapter
from app.adapters.domains.pet_supplies import PetSuppliesDomainAdapter
from app.db.base import Base
from app.db.models.core import KnowledgeSource, Product
from app.db.repositories.sqlalchemy import SqlAlchemyProductRepository
from app.rag.in_memory import InMemoryKnowledgeStore


def test_pet_supplies_adapter_seeds_from_imported_real_data() -> None:
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
                payload_json={
                    "name": "Reflective Dog Harness",
                    "category": "Harnesses",
                    "description": "Built for daily walks.",
                    "attributes": {"parent_asin": "PARENT-1"},
                    "materials": [],
                    "dimensions": {},
                    "features": ["Reflective trim"],
                    "use_scenarios": [],
                    "target_market": "amazon_us",
                    "target_audience": ["Dogs"],
                    "target_price": "24.95",
                    "target_currency": "USD",
                    "known_risks": [],
                    "data_mode": "real",
                },
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

        adapter = PetSuppliesDomainAdapter()
        knowledge_store = InMemoryKnowledgeStore()
        product = adapter.seed(session, SqlAlchemyProductRepository(session), knowledge_store)

        assert isinstance(adapter, DomainAdapter)
        assert adapter.domain_name == "pet_supplies"
        assert product.product_id == "pet-product-1"
        assert product.data_origin.value == "real"
        assert len(knowledge_store.documents) == 1
        assert knowledge_store.documents[0].document_id == "knowledge-1"
