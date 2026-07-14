import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter


@dataclass(slots=True)
class PrefilterSummary:
    total: int = 0
    kept: int = 0
    dropped_invalid_json: int = 0
    dropped_non_pet_supplies: int = 0
    dropped_missing_price: int = 0
    dropped_missing_title: int = 0
    dropped_missing_parent_asin: int = 0


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


def _has_non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_pet_supplies_record(record: dict[str, object]) -> bool:
    main_category = record.get("main_category")
    if main_category == "Pet Supplies":
        return True

    categories = record.get("categories")
    if not isinstance(categories, list):
        return False
    return any(category == "Pet Supplies" for category in categories)


def prefilter_pet_supplies(input_path: Path, output_path: Path) -> PrefilterSummary:
    summary = PrefilterSummary()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tracker = ProgressTracker(
        label="metadata_prefilter",
        total_bytes=input_path.stat().st_size,
        interval=5000,
    )
    tracker.start()

    with input_path.open("rb") as source, output_path.open("w", encoding="utf-8") as target:
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

            if not _is_pet_supplies_record(record):
                summary.dropped_non_pet_supplies += 1
                continue

            if record.get("price") is None:
                summary.dropped_missing_price += 1
                continue

            if not _has_non_empty_text(record.get("title")):
                summary.dropped_missing_title += 1
                continue

            if not _has_non_empty_text(record.get("parent_asin")):
                summary.dropped_missing_parent_asin += 1
                continue

            target.write(json.dumps(record, ensure_ascii=False))
            target.write("\n")
            summary.kept += 1

    tracker.render(final=True)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prefilter the raw pet supplies metadata JSONL file.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/meta_Pet_Supplies.jsonl/meta_Pet_Supplies.jsonl"),
        help="Path to the raw metadata JSONL file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/filtered/meta_pet_supplies_prefiltered.jsonl"),
        help="Path to the filtered JSONL output file.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = prefilter_pet_supplies(args.input, args.output)
    print(f"input_path={args.input}")
    print(f"output_path={args.output}")
    print(f"total={summary.total}")
    print(f"kept={summary.kept}")
    print(f"dropped_invalid_json={summary.dropped_invalid_json}")
    print(f"dropped_non_pet_supplies={summary.dropped_non_pet_supplies}")
    print(f"dropped_missing_price={summary.dropped_missing_price}")
    print(f"dropped_missing_title={summary.dropped_missing_title}")
    print(f"dropped_missing_parent_asin={summary.dropped_missing_parent_asin}")


if __name__ == "__main__":
    main()
