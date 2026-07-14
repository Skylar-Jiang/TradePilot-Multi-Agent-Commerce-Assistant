import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter


@dataclass(slots=True)
class ReviewPrefilterSummary:
    total: int = 0
    kept: int = 0
    product_parent_asins: int = 0
    dropped_invalid_json: int = 0
    dropped_missing_title: int = 0
    dropped_missing_text: int = 0
    dropped_missing_rating: int = 0
    dropped_missing_parent_asin: int = 0
    dropped_not_in_product_set: int = 0
    dropped_exceeds_max_reviews_per_parent: int = 0


@dataclass(slots=True)
class ProgressTracker:
    label: str
    total_bytes: int
    interval: int = 5000
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


def _has_non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_product_parent_asins(product_input_path: Path) -> set[str]:
    parent_asins: set[str] = set()
    with product_input_path.open("r", encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            parent_asin = record.get("parent_asin")
            if _has_non_empty_text(parent_asin):
                parent_asins.add(parent_asin.strip())
    return parent_asins


def prefilter_pet_supplies_reviews(
    review_input_path: Path,
    product_input_path: Path,
    output_path: Path,
    *,
    max_reviews_per_parent: int | None = None,
) -> ReviewPrefilterSummary:
    summary = ReviewPrefilterSummary()
    allowed_parent_asins = load_product_parent_asins(product_input_path)
    kept_counts_by_parent: dict[str, int] = {}
    summary.product_parent_asins = len(allowed_parent_asins)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tracker = ProgressTracker(
        label="review_prefilter",
        total_bytes=review_input_path.stat().st_size,
        interval=5000,
    )
    tracker.start()

    with review_input_path.open("rb") as source, output_path.open("w", encoding="utf-8") as target:
        for raw_line in source:
            summary.total += 1
            tracker.advance(raw_line)
            line = raw_line.decode("utf-8").strip()
            if not line:
                summary.dropped_invalid_json += 1
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                summary.dropped_invalid_json += 1
                continue

            if not isinstance(record, dict):
                summary.dropped_invalid_json += 1
                continue

            parent_asin = record.get("parent_asin")
            if not _has_non_empty_text(parent_asin):
                summary.dropped_missing_parent_asin += 1
                continue
            normalized_parent_asin = parent_asin.strip()

            if normalized_parent_asin not in allowed_parent_asins:
                summary.dropped_not_in_product_set += 1
                continue

            if record.get("rating") is None:
                summary.dropped_missing_rating += 1
                continue

            if not _has_non_empty_text(record.get("title")):
                summary.dropped_missing_title += 1
                continue

            if not _has_non_empty_text(record.get("text")):
                summary.dropped_missing_text += 1
                continue

            if max_reviews_per_parent is not None:
                kept_for_parent = kept_counts_by_parent.get(normalized_parent_asin, 0)
                if kept_for_parent >= max_reviews_per_parent:
                    summary.dropped_exceeds_max_reviews_per_parent += 1
                    continue

            record["parent_asin"] = normalized_parent_asin
            target.write(json.dumps(record, ensure_ascii=False))
            target.write("\n")
            summary.kept += 1
            kept_counts_by_parent[normalized_parent_asin] = kept_counts_by_parent.get(normalized_parent_asin, 0) + 1

    tracker.render(final=True)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prefilter the raw pet supplies reviews JSONL file.")
    parser.add_argument(
        "--reviews-input",
        type=Path,
        default=Path("data/Pet_Supplies.jsonl/Pet_Supplies.jsonl"),
        help="Path to the raw pet supplies reviews JSONL file.",
    )
    parser.add_argument(
        "--products-input",
        type=Path,
        default=Path("data/filtered/meta_pet_supplies_prefiltered.jsonl"),
        help="Path to the filtered pet supplies product metadata JSONL file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/filtered/pet_supplies_reviews_prefiltered.jsonl"),
        help="Path to the filtered reviews JSONL output file.",
    )
    parser.add_argument(
        "--max-reviews-per-parent",
        type=int,
        default=None,
        help="Optional cap on how many reviews to keep per parent_asin.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = prefilter_pet_supplies_reviews(
        args.reviews_input,
        args.products_input,
        args.output,
        max_reviews_per_parent=args.max_reviews_per_parent,
    )
    print(f"reviews_input_path={args.reviews_input}")
    print(f"products_input_path={args.products_input}")
    print(f"output_path={args.output}")
    print(f"max_reviews_per_parent={args.max_reviews_per_parent}")
    print(f"product_parent_asins={summary.product_parent_asins}")
    print(f"total={summary.total}")
    print(f"kept={summary.kept}")
    print(f"dropped_invalid_json={summary.dropped_invalid_json}")
    print(f"dropped_missing_title={summary.dropped_missing_title}")
    print(f"dropped_missing_text={summary.dropped_missing_text}")
    print(f"dropped_missing_rating={summary.dropped_missing_rating}")
    print(f"dropped_missing_parent_asin={summary.dropped_missing_parent_asin}")
    print(f"dropped_not_in_product_set={summary.dropped_not_in_product_set}")
    print(f"dropped_exceeds_max_reviews_per_parent={summary.dropped_exceeds_max_reviews_per_parent}")


if __name__ == "__main__":
    main()
