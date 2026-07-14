from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.core import CompetitorOffer, KnowledgeSource, Product, Review
from scripts.domain_imports.clean_pet_supplies import clean_pet_supplies


def test_clean_pet_supplies_normalizes_imported_records() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            Product(
                product_id="product-1",
                name="  Reflective   Dog Harness  ",
                category=" Harnesses ",
                data_mode="real",
                data_origin="real",
                attributes_json={
                    "parent_asin": " PARENT-1 ",
                    "store": " Hurtta ",
                    "brand": "",
                    "main_category": " Pet Supplies ",
                    "categories": ["Pet Supplies", " Dogs ", "Harnesses", "Dogs"],
                    "details": {"Brand": " Hurtta ", "Material": " Neoprene ", "Target Species": " Dog, Puppy "},
                    "image_count": "3",
                    "video_count": "0",
                    "price": "24.950",
                    "average_rating": "4.400",
                    "rating_number": "166",
                },
                metadata_json={"source_file": "x"},
                payload_json={
                    "name": "  Reflective   Dog Harness  ",
                    "category": " Harnesses ",
                    "description": "  Built   for daily walks. ",
                    "attributes": {"parent_asin": " PARENT-1 "},
                    "materials": [],
                    "dimensions": {},
                    "features": [" Reflective trim ", " Adjustable chest "],
                    "use_scenarios": [],
                    "target_market": "",
                    "target_audience": [],
                    "target_price": "24.950",
                    "target_currency": "USD",
                    "known_risks": [],
                    "data_mode": "real",
                },
            )
        )
        session.add(
            CompetitorOffer(
                offer_id="offer-1",
                product_id="product-1",
                data_origin="real",
                attributes_json={
                    "parent_asin": " PARENT-1 ",
                    "store": " Hurtta ",
                    "brand": "",
                    "main_category": " Pet Supplies ",
                    "categories": ["Pet Supplies", " Dogs ", "Harnesses"],
                    "price": "24.950",
                    "average_rating": "4.400",
                    "rating_number": "166",
                },
            )
        )
        session.add(
            Review(
                review_id="review-1",
                product_id="product-1",
                content=" Works   great \n\n My dog loves it. ",
                data_origin="real",
                metadata_json={
                    "review_title": " Works   great ",
                    "asin": " ASIN-1 ",
                    "parent_asin": " PARENT-1 ",
                    "user_id": " USER-1 ",
                    "helpful_vote": "2",
                    "verified_purchase": 1,
                    "rating": "5.0",
                    "image_count": "0",
                },
            )
        )
        session.add(
            KnowledgeSource(
                source_id="knowledge-1",
                product_id="product-1",
                knowledge_type="product_knowledge",
                content=" stale ",
                data_origin="real",
                metadata_json={"source_name": "  Reflective   Dog Harness  ", "parent_asin": " PARENT-1 "},
            )
        )
        session.commit()

        summary = clean_pet_supplies(session)

        assert summary.scanned_products == 1
        assert summary.updated_products == 1
        assert summary.scanned_offers == 1
        assert summary.updated_offers == 1
        assert summary.scanned_reviews == 1
        assert summary.updated_reviews == 1
        assert summary.scanned_knowledge_sources == 1
        assert summary.updated_knowledge_sources == 1

        product = session.get(Product, "product-1")
        assert product is not None
        assert product.name == "Reflective Dog Harness"
        assert product.category == "Harnesses"
        assert product.attributes_json["brand"] == "Hurtta"
        assert product.attributes_json["categories"] == ["Pet Supplies", "Dogs", "Harnesses"]
        assert product.attributes_json["species"] == ["Dogs", "Dog", "Puppy"]
        assert product.attributes_json["image_count"] == 3
        assert product.attributes_json["price"] == "24.950"
        assert product.metadata_json["clean_stage"] == "pet_supplies_normalized"
        assert product.payload_json["target_market"] == "amazon_us"
        assert product.payload_json["features"] == ["Reflective trim", "Adjustable chest"]

        offer = session.get(CompetitorOffer, "offer-1")
        assert offer is not None
        assert offer.attributes_json["brand"] == "Hurtta"
        assert offer.attributes_json["categories"] == ["Pet Supplies", "Dogs", "Harnesses"]
        assert offer.attributes_json["subcategory_path"] == ["Dogs", "Harnesses"]

        review = session.get(Review, "review-1")
        assert review is not None
        assert review.content == "Works great My dog loves it."
        assert review.metadata_json["review_title"] == "Works great"
        assert review.metadata_json["helpful_vote"] == 2
        assert review.metadata_json["verified_purchase"] is True
        assert review.metadata_json["clean_stage"] == "pet_supplies_normalized"

        knowledge = session.scalars(select(KnowledgeSource)).first()
        assert knowledge is not None
        assert "Title: Reflective Dog Harness" in knowledge.content
        assert knowledge.metadata_json["source_name"] == "Reflective Dog Harness"
        assert knowledge.metadata_json["clean_stage"] == "pet_supplies_normalized"
