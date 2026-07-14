from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DataOrigin, KnowledgeType
from app.db.models.core import KnowledgeSource, Product
from app.db.repositories.protocols import ProductRepository
from app.rag.contracts import KnowledgeDocument, KnowledgeStore
from app.schemas.common import DataGap
from app.schemas.product import ProductProfile

PET_METADATA_SOURCE_FILE = "data/filtered/meta_pet_supplies_prefiltered.jsonl"


class PetSuppliesDomainAdapter:
    domain_name = "pet_supplies"

    def seed(
        self,
        session: Session,
        products: ProductRepository,
        knowledge_store: KnowledgeStore,
    ) -> ProductProfile:
        statement = (
            select(Product)
            .where(Product.data_origin == DataOrigin.REAL.value)
            .order_by(Product.created_at)
        )
        selected: Product | None = None
        for record in session.scalars(statement):
            metadata = record.metadata_json if isinstance(record.metadata_json, dict) else {}
            if metadata.get("source_file") == PET_METADATA_SOURCE_FILE:
                selected = record
                break

        if selected is None:
            raise ValueError("No imported pet supplies product exists. Import and clean pet supplies data first.")

        product = products.get(selected.product_id)

        documents = [
            KnowledgeDocument(
                document_id=source.source_id,
                product_id=source.product_id or product.product_id,
                knowledge_type=KnowledgeType(source.knowledge_type),
                content=source.content,
                source_name=(source.metadata_json or {}).get("source_name", product.name),
                data_origin=DataOrigin(source.data_origin),
                metadata=source.metadata_json or {},
            )
            for source in session.scalars(
                select(KnowledgeSource)
                .where(KnowledgeSource.product_id == product.product_id)
                .order_by(KnowledgeSource.source_id)
            ).all()
            if source.product_id is not None
        ]
        if documents:
            knowledge_store.ingest(documents)
            return product

        return product.model_copy(
            update={
                "data_gaps": [
                    *product.data_gaps,
                    DataGap(
                        code="pet_supplies_knowledge_missing",
                        field="knowledge_sources",
                        reason="Imported pet supplies product has no knowledge documents to ingest.",
                        required_for="RAG-backed analysis",
                    ),
                ]
            }
        )
