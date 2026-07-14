import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.core import CompetitorOffer, KnowledgeSource, Product, Review
from scripts.domain_imports.import_pet_supplies import import_pet_supplies


def test_import_pet_supplies_creates_products_offers_reviews_and_knowledge(tmp_path: Path) -> None:
    metadata_input_path = tmp_path / "metadata.jsonl"
    reviews_input_path = tmp_path / "reviews.jsonl"
    metadata_input_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "title": "Reflective Dog Harness",
                        "main_category": "Pet Supplies",
                        "average_rating": 4.4,
                        "rating_number": 166,
                        "features": ["Reflective trim", "Adjustable chest"],
                        "description": ["Built for daily walks."],
                        "price": 24.95,
                        "images": [{"variant": "MAIN"}],
                        "videos": [],
                        "store": "Hurtta",
                        "categories": ["Pet Supplies", "Dogs", "Harnesses"],
                        "details": {"Brand": "Hurtta", "Material": "Neoprene"},
                        "parent_asin": "PARENT-1",
                    }
                ),
                json.dumps(
                    {
                        "title": "Ceramic Pet Bowls",
                        "main_category": "Pet Supplies",
                        "average_rating": 4.6,
                        "rating_number": 100,
                        "features": ["Ceramic", "Raised stand"],
                        "description": ["Good for cats and dogs."],
                        "price": 32.88,
                        "images": [{"variant": "MAIN"}],
                        "videos": [{"title": "demo"}],
                        "store": "FIVEAGE",
                        "categories": ["Pet Supplies", "Dogs", "Bowls & Dishes"],
                        "details": {"Brand": "FIVEAGE", "Material": "Ceramic"},
                        "parent_asin": "PARENT-2",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    reviews_input_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "rating": 5.0,
                        "title": "Works great",
                        "text": "My dog loves it.",
                        "images": [],
                        "asin": "ASIN-1",
                        "parent_asin": "PARENT-1",
                        "user_id": "USER-1",
                        "timestamp": 1,
                        "helpful_vote": 2,
                        "verified_purchase": True,
                    }
                ),
                json.dumps(
                    {
                        "rating": 3.0,
                        "title": "Okay",
                        "text": "Good enough for the price.",
                        "images": [],
                        "asin": "ASIN-2",
                        "parent_asin": "PARENT-2",
                        "user_id": "USER-2",
                        "timestamp": 2,
                        "helpful_vote": 0,
                        "verified_purchase": False,
                    }
                ),
                json.dumps(
                    {
                        "rating": 5.0,
                        "title": "Works great",
                        "text": "My dog loves it in a second room.",
                        "images": [],
                        "asin": "ASIN-1",
                        "parent_asin": "PARENT-1",
                        "user_id": "USER-1",
                        "timestamp": 1,
                        "helpful_vote": 2,
                        "verified_purchase": True,
                    }
                ),
                json.dumps(
                    {
                        "rating": 1.0,
                        "title": "Orphan",
                        "text": "Should not be imported.",
                        "asin": "ASIN-3",
                        "parent_asin": "MISSING-PARENT",
                        "user_id": "USER-3",
                        "timestamp": 3,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        summary = import_pet_supplies(session, metadata_input_path, reviews_input_path)
        repeated = import_pet_supplies(session, metadata_input_path, reviews_input_path)

        assert summary.metadata_total == 2
        assert summary.review_total == 4
        assert summary.imported_products == 2
        assert summary.imported_offers == 2
        assert summary.imported_reviews == 3
        assert summary.skipped_duplicate_reviews == 0
        assert summary.imported_knowledge_sources == 2
        assert summary.skipped_reviews_without_matching_product == 1

        assert repeated.imported_products == 0
        assert repeated.updated_products == 2
        assert repeated.imported_reviews == 0
        assert repeated.updated_reviews == 3

        assert session.scalar(select(func.count()).select_from(Product)) == 2
        assert session.scalar(select(func.count()).select_from(CompetitorOffer)) == 2
        assert session.scalar(select(func.count()).select_from(Review)) == 3
        assert session.scalar(select(func.count()).select_from(KnowledgeSource)) == 2

        product = session.scalars(select(Product).order_by(Product.name)).first()
        assert product is not None
        assert product.data_mode == "real"
        assert product.data_origin == "real"
        assert product.attributes_json["parent_asin"] in {"PARENT-1", "PARENT-2"}

        knowledge = session.scalars(select(KnowledgeSource).order_by(KnowledgeSource.source_id)).first()
        assert knowledge is not None
        assert knowledge.knowledge_type == "product_knowledge"
        assert "Title:" in knowledge.content
