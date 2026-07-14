import argparse
import json
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session  # noqa: E402

Product: Any = None
CompetitorOffer: Any = None
KnowledgeSource: Any = None
Review: Any = None
SessionLocal: Any = None
get_settings: Any = None
upgrade_database: Any = None
DATA_MODE_REAL = "real"
DATA_ORIGIN_REAL = "real"
KNOWLEDGE_TYPE_PRODUCT = "product_knowledge"


@dataclass(slots=True)
class ImportSummary:
    metadata_total: int = 0
    review_total: int = 0
    imported_products: int = 0
    updated_products: int = 0
    imported_offers: int = 0
    updated_offers: int = 0
    imported_reviews: int = 0
    updated_reviews: int = 0
    skipped_duplicate_reviews: int = 0
    imported_knowledge_sources: int = 0
    updated_knowledge_sources: int = 0
    skipped_invalid_metadata: int = 0
    skipped_invalid_reviews: int = 0
    skipped_reviews_without_matching_product: int = 0


@dataclass(slots=True)
class ProgressTracker:
    label: str
    total_bytes: int
    interval: int = 2000
    processed_items: int = 0
    processed_bytes: int = 0
    started_at: float = 0.0

    def start(self) -> None:
        self.started_at = perf_counter()

    def advance(self, raw_line: bytes) -> None:
        self.processed_items += 1
        self.processed_bytes += len(raw_line)
        if self.processed_items == 1 or self.processed_items % self.interval == 0:
            self.render()

    def render(self, *, final: bool = False) -> None:
        percent = 0.0 if self.total_bytes == 0 else min(self.processed_bytes / self.total_bytes, 1.0)
        filled = int(percent * 20)
        bar = "#" * filled + "-" * (20 - filled)
        elapsed = max(perf_counter() - self.started_at, 0.001)
        rate = self.processed_items / elapsed
        suffix = "\n" if final else "\r"
        print(
            f"{self.label}: [{bar}] {percent * 100:6.2f}% "
            f"items={self.processed_items} rate={rate:,.1f}/s",
            end=suffix,
            flush=True,
        )


def _ensure_runtime_imports() -> None:
    global CompetitorOffer
    global KnowledgeSource
    global Product
    global Review
    global SessionLocal
    global get_settings
    global upgrade_database
    if Product is not None:
        return

    from app.core.config import get_settings as _get_settings  # noqa: WPS433
    from app.db.migrations import upgrade_database as _upgrade_database  # noqa: WPS433
    from app.db.models.core import CompetitorOffer as _CompetitorOffer  # noqa: WPS433
    from app.db.models.core import KnowledgeSource as _KnowledgeSource  # noqa: WPS433
    from app.db.models.core import Product as _Product  # noqa: WPS433
    from app.db.models.core import Review as _Review  # noqa: WPS433
    from app.db.session import SessionLocal as _SessionLocal  # noqa: WPS433

    Product = _Product
    CompetitorOffer = _CompetitorOffer
    KnowledgeSource = _KnowledgeSource
    Review = _Review
    SessionLocal = _SessionLocal
    get_settings = _get_settings
    upgrade_database = _upgrade_database


def deterministic_id(prefix: str, *parts: object) -> str:
    joined = "|".join(str(part) for part in parts)
    return str(uuid5(NAMESPACE_URL, f"tradepilot:{prefix}:{joined}"))


def _has_non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalize_text(value: object, *, limit: int | None = None) -> str:
    if isinstance(value, str):
        normalized = " ".join(value.split())
    else:
        normalized = ""
    if limit is not None:
        return normalized[:limit]
    return normalized


def _normalize_categories(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    categories: list[str] = []
    for item in value:
        if _has_non_empty_text(item):
            categories.append(item.strip())
    return categories


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if _has_non_empty_text(item):
            normalized.append(" ".join(item.split()))
    return normalized


def _normalize_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _normalize_decimal(value: object) -> str | None:
    if value is None or value == "":
        return None
    try:
        return str(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return None


def _normalize_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_materials(details: dict[str, object]) -> list[str]:
    material = details.get("Material")
    if not _has_non_empty_text(material):
        return []
    return [material.strip()]


def _extract_dimensions(details: dict[str, object]) -> dict[str, object]:
    dimensions: dict[str, object] = {}
    if _has_non_empty_text(details.get("Product Dimensions")):
        dimensions["product_dimensions"] = details["Product Dimensions"].strip()
    if _has_non_empty_text(details.get("Package Dimensions")):
        dimensions["package_dimensions"] = details["Package Dimensions"].strip()
    return dimensions


def _extract_target_audience(categories: list[str], details: dict[str, object]) -> list[str]:
    audience: list[str] = []
    if len(categories) > 1:
        audience.append(categories[1])
    target_species = details.get("Target Species")
    if _has_non_empty_text(target_species):
        for part in str(target_species).split(","):
            normalized = _normalize_text(part)
            if normalized and normalized not in audience:
                audience.append(normalized)
    return audience


def _build_description(record: dict[str, object]) -> str:
    description = record.get("description")
    if isinstance(description, list):
        parts = [_normalize_text(item) for item in description if _has_non_empty_text(item)]
        return "\n".join(parts)
    return _normalize_text(description)


def _build_product_payload(record: dict[str, object]) -> dict[str, object]:
    title = _normalize_text(record.get("title"), limit=200)
    categories = _normalize_categories(record.get("categories"))
    details = _normalize_dict(record.get("details"))
    features = _normalize_string_list(record.get("features"))
    brand = _normalize_text(details.get("Brand")) or _normalize_text(record.get("store"))
    price = _normalize_decimal(record.get("price"))

    category = categories[-1] if categories else _normalize_text(record.get("main_category"), limit=120)
    category = category[:120] or "pet-supplies"
    attributes = {
        "parent_asin": _normalize_text(record.get("parent_asin")),
        "store": _normalize_text(record.get("store")),
        "brand": brand,
        "main_category": _normalize_text(record.get("main_category")),
        "categories": categories,
        "details": details,
        "image_count": len(record.get("images", [])) if isinstance(record.get("images"), list) else 0,
        "video_count": len(record.get("videos", [])) if isinstance(record.get("videos"), list) else 0,
        "average_rating": record.get("average_rating"),
        "rating_number": record.get("rating_number"),
        "price": price,
    }
    return {
        "name": title,
        "category": category,
        "description": _build_description(record),
        "attributes": attributes,
        "materials": _extract_materials(details),
        "dimensions": _extract_dimensions(details),
        "features": features,
        "use_scenarios": [],
        "target_market": "amazon_us",
        "target_audience": _extract_target_audience(categories, details),
        "target_price": price,
        "target_currency": "USD" if price is not None else None,
        "known_risks": [],
        "data_mode": DATA_MODE_REAL,
    }


def _build_offer_attributes(record: dict[str, object]) -> dict[str, object]:
    details = _normalize_dict(record.get("details"))
    return {
        "parent_asin": _normalize_text(record.get("parent_asin")),
        "store": _normalize_text(record.get("store")),
        "brand": _normalize_text(details.get("Brand")) or _normalize_text(record.get("store")),
        "main_category": _normalize_text(record.get("main_category")),
        "categories": _normalize_categories(record.get("categories")),
        "price": _normalize_decimal(record.get("price")),
        "average_rating": _normalize_decimal(record.get("average_rating")),
        "rating_number": _normalize_int(record.get("rating_number")),
    }


def _build_product_knowledge_content(record: dict[str, object]) -> str:
    title = _normalize_text(record.get("title"))
    features = _normalize_string_list(record.get("features"))
    description = _build_description(record)
    details = _normalize_dict(record.get("details"))

    sections = [f"Title: {title}"]
    if features:
        sections.append("Features:\n- " + "\n- ".join(features))
    if description:
        sections.append(f"Description:\n{description}")
    if details:
        detail_lines = [f"{key}: {value}" for key, value in details.items() if _has_non_empty_text(value)]
        if detail_lines:
            sections.append("Details:\n- " + "\n- ".join(detail_lines))
    return "\n\n".join(sections)


def _upsert_product_record(
    session: Session,
    record: dict[str, object],
    line_number: int,
    summary: ImportSummary,
) -> str:
    parent_asin = _normalize_text(record.get("parent_asin"))
    product_id = deterministic_id("product", parent_asin)
    product = session.get(Product, product_id)
    payload = _build_product_payload(record)

    if product is None:
        product = Product(product_id=product_id)
        session.add(product)
        summary.imported_products += 1
    else:
        summary.updated_products += 1

    product.name = payload["name"]
    product.category = payload["category"]
    product.data_mode = DATA_MODE_REAL
    product.data_origin = DATA_ORIGIN_REAL
    product.attributes_json = payload["attributes"]
    product.metadata_json = {
        "source_file": "data/filtered/meta_pet_supplies_prefiltered.jsonl",
        "source_line": line_number,
    }
    product.payload_json = payload
    return product_id


def _upsert_offer_record(session: Session, product_id: str, record: dict[str, object], summary: ImportSummary) -> None:
    offer_id = deterministic_id("offer", _normalize_text(record.get("parent_asin")))
    offer = session.get(CompetitorOffer, offer_id)
    if offer is None:
        offer = CompetitorOffer(offer_id=offer_id)
        session.add(offer)
        summary.imported_offers += 1
    else:
        summary.updated_offers += 1

    offer.product_id = product_id
    offer.data_origin = DATA_ORIGIN_REAL
    offer.attributes_json = _build_offer_attributes(record)


def _upsert_product_knowledge_record(
    session: Session,
    product_id: str,
    record: dict[str, object],
    line_number: int,
    summary: ImportSummary,
) -> None:
    source_id = deterministic_id("knowledge-product", _normalize_text(record.get("parent_asin")))
    source = session.get(KnowledgeSource, source_id)
    if source is None:
        source = KnowledgeSource(source_id=source_id)
        session.add(source)
        summary.imported_knowledge_sources += 1
    else:
        summary.updated_knowledge_sources += 1

    source.product_id = product_id
    source.knowledge_type = KNOWLEDGE_TYPE_PRODUCT
    source.content = _build_product_knowledge_content(record)
    source.data_origin = DATA_ORIGIN_REAL
    source.metadata_json = {
        "source_name": _normalize_text(record.get("title")),
        "source_file": "data/filtered/meta_pet_supplies_prefiltered.jsonl",
        "source_line": line_number,
        "parent_asin": _normalize_text(record.get("parent_asin")),
    }


def import_filtered_products(
    session: Session,
    metadata_input_path: Path,
    summary: ImportSummary,
    *,
    commit_every: int = 1000,
) -> set[str]:
    imported_parent_asins: set[str] = set()
    tracker = ProgressTracker(
        label="metadata_import",
        total_bytes=metadata_input_path.stat().st_size,
        interval=2000,
    )
    tracker.start()
    with metadata_input_path.open("rb") as source:
        for line_number, raw_line in enumerate(source, start=1):
            summary.metadata_total += 1
            tracker.advance(raw_line)
            line = raw_line.decode("utf-8").strip()
            if not line:
                summary.skipped_invalid_metadata += 1
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                summary.skipped_invalid_metadata += 1
                continue
            if not isinstance(record, dict):
                summary.skipped_invalid_metadata += 1
                continue
            if not _has_non_empty_text(record.get("parent_asin")) or not _has_non_empty_text(record.get("title")):
                summary.skipped_invalid_metadata += 1
                continue

            product_id = _upsert_product_record(session, record, line_number, summary)
            _upsert_offer_record(session, product_id, record, summary)
            _upsert_product_knowledge_record(session, product_id, record, line_number, summary)
            imported_parent_asins.add(_normalize_text(record.get("parent_asin")))

            if line_number % commit_every == 0:
                session.commit()

    session.commit()
    tracker.render(final=True)
    return imported_parent_asins


def _build_review_content(record: dict[str, object]) -> str:
    title = _normalize_text(record.get("title"))
    text = _normalize_text(record.get("text"))
    if title and text:
        return f"{title}\n\n{text}"
    return title or text


def _upsert_review_record(
    session: Session,
    review_id: str,
    product_id: str,
    record: dict[str, object],
    line_number: int,
    summary: ImportSummary,
) -> None:
    review = session.get(Review, review_id)
    if review is None:
        review = Review(review_id=review_id)
        session.add(review)
        summary.imported_reviews += 1
    else:
        summary.updated_reviews += 1

    images = record.get("images")
    review.product_id = product_id
    review.content = _build_review_content(record)
    review.data_origin = DATA_ORIGIN_REAL
    review.metadata_json = {
        "review_title": _normalize_text(record.get("title")),
        "asin": _normalize_text(record.get("asin")),
        "parent_asin": _normalize_text(record.get("parent_asin")),
        "user_id": _normalize_text(record.get("user_id")),
        "timestamp": record.get("timestamp"),
        "helpful_vote": _normalize_int(record.get("helpful_vote")) or 0,
        "verified_purchase": bool(record.get("verified_purchase")),
        "rating": _normalize_decimal(record.get("rating")),
        "image_count": len(images) if isinstance(images, list) else 0,
        "source_file": "data/filtered/pet_supplies_reviews_prefiltered.jsonl",
        "source_line": line_number,
    }


def import_filtered_reviews(
    session: Session,
    reviews_input_path: Path,
    imported_parent_asins: set[str],
    summary: ImportSummary,
    *,
    commit_every: int = 2000,
) -> None:
    seen_review_ids: set[str] = set()
    tracker = ProgressTracker(
        label="review_import",
        total_bytes=reviews_input_path.stat().st_size,
        interval=5000,
    )
    tracker.start()
    with reviews_input_path.open("rb") as source:
        for line_number, raw_line in enumerate(source, start=1):
            summary.review_total += 1
            tracker.advance(raw_line)
            line = raw_line.decode("utf-8").strip()
            if not line:
                summary.skipped_invalid_reviews += 1
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                summary.skipped_invalid_reviews += 1
                continue
            if not isinstance(record, dict):
                summary.skipped_invalid_reviews += 1
                continue

            parent_asin = _normalize_text(record.get("parent_asin"))
            if not parent_asin or parent_asin not in imported_parent_asins:
                summary.skipped_reviews_without_matching_product += 1
                continue

            review_id = deterministic_id(
                "review",
                parent_asin,
                _normalize_text(record.get("asin")),
                _normalize_text(record.get("user_id")),
                record.get("timestamp"),
                _normalize_text(record.get("title")),
                _normalize_text(record.get("text")),
            )
            if review_id in seen_review_ids:
                summary.skipped_duplicate_reviews += 1
                continue
            seen_review_ids.add(review_id)

            product_id = deterministic_id("product", parent_asin)
            _upsert_review_record(session, review_id, product_id, record, line_number, summary)

            if line_number % commit_every == 0:
                session.commit()

    session.commit()
    tracker.render(final=True)


def import_pet_supplies(
    session: Session,
    metadata_input_path: Path,
    reviews_input_path: Path,
) -> ImportSummary:
    _ensure_runtime_imports()
    summary = ImportSummary()
    imported_parent_asins = import_filtered_products(session, metadata_input_path, summary)
    import_filtered_reviews(session, reviews_input_path, imported_parent_asins, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import filtered pet supplies data into the TradePilot database.")
    parser.add_argument(
        "--metadata-input",
        type=Path,
        default=Path("data/filtered/meta_pet_supplies_prefiltered.jsonl"),
        help="Path to the filtered pet supplies metadata JSONL file.",
    )
    parser.add_argument(
        "--reviews-input",
        type=Path,
        default=Path("data/filtered/pet_supplies_reviews_prefiltered.jsonl"),
        help="Path to the filtered pet supplies reviews JSONL file.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    print("import_pet_supplies: starting", flush=True)
    print(f"metadata_input_path={args.metadata_input}", flush=True)
    print(f"reviews_input_path={args.reviews_input}", flush=True)
    print(f"metadata_input_exists={args.metadata_input.exists()}", flush=True)
    print(f"reviews_input_exists={args.reviews_input.exists()}", flush=True)
    print("import_pet_supplies: importing runtime dependencies", flush=True)
    _ensure_runtime_imports()
    print("import_pet_supplies: runtime dependencies ready", flush=True)
    print("import_pet_supplies: loading settings", flush=True)
    settings = get_settings()
    print(f"database_url={settings.database_url}", flush=True)
    print("import_pet_supplies: upgrading database", flush=True)
    upgrade_database(settings.database_url)
    print("import_pet_supplies: database ready", flush=True)
    print("import_pet_supplies: opening session", flush=True)
    with SessionLocal() as session:
        print("import_pet_supplies: session opened", flush=True)
        print("import_pet_supplies: starting metadata import", flush=True)
        summary = import_pet_supplies(session, args.metadata_input, args.reviews_input)

    print("import_pet_supplies: finished", flush=True)
    print(f"metadata_total={summary.metadata_total}")
    print(f"review_total={summary.review_total}")
    print(f"imported_products={summary.imported_products}")
    print(f"updated_products={summary.updated_products}")
    print(f"imported_offers={summary.imported_offers}")
    print(f"updated_offers={summary.updated_offers}")
    print(f"imported_reviews={summary.imported_reviews}")
    print(f"updated_reviews={summary.updated_reviews}")
    print(f"skipped_duplicate_reviews={summary.skipped_duplicate_reviews}")
    print(f"imported_knowledge_sources={summary.imported_knowledge_sources}")
    print(f"updated_knowledge_sources={summary.updated_knowledge_sources}")
    print(f"skipped_invalid_metadata={summary.skipped_invalid_metadata}")
    print(f"skipped_invalid_reviews={summary.skipped_invalid_reviews}")
    print(f"skipped_reviews_without_matching_product={summary.skipped_reviews_without_matching_product}")


if __name__ == "__main__":
    main()
