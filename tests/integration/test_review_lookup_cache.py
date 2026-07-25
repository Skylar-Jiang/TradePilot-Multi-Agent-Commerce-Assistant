import json
import os
import sqlite3
from pathlib import Path

import pytest

from app.core.exceptions import DataPreparationRequiredError
from app.domain.review_lookup import ReviewLookup


def _review(parent_asin: str, index: int) -> dict[str, object]:
    return {
        "parent_asin": parent_asin,
        "asin": f"ASIN-{parent_asin}",
        "user_id": f"USER-{index}",
        "timestamp": index,
        "rating": 4.0,
        "title": f"Review {index}",
        "text": f"Original review text {index}",
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_review_lookup_reads_only_selected_parent_rows_by_original_offsets(tmp_path: Path) -> None:
    source = tmp_path / "reviews.jsonl"
    cache_path = tmp_path / "cache" / "review_lookup.sqlite"
    _write_jsonl(source, [_review("P1", 1), _review("P2", 2), _review("P2", 3), _review("P3", 4)])

    first = ReviewLookup.build(source, cache_path)
    second = ReviewLookup.build(source, cache_path)
    rows = second.read(["P2"])

    assert first.rebuilt is True
    assert first.rows_scanned == 4
    assert first.review_count == 4
    assert first.parent_count == 3
    assert first.build_duration_ms >= 0
    assert second.rebuilt is False
    assert second.rows_scanned == 0
    assert [row.parent_asin for row in rows] == ["P2", "P2"]
    assert [row.source_row for row in rows] == [2, 3]
    assert [row.record["text"] for row in rows] == ["Original review text 2", "Original review text 3"]

    with sqlite3.connect(cache_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(review_offsets)")}
    assert "content" not in columns
    assert "record_json" not in columns


def test_review_lookup_rebuilds_when_source_changes_and_caps_total_rows(tmp_path: Path) -> None:
    source = tmp_path / "reviews.jsonl"
    cache_path = tmp_path / "review_lookup.sqlite"
    _write_jsonl(source, [_review("P1", 1)])
    ReviewLookup.build(source, cache_path)
    _write_jsonl(source, [_review("P1", 1), _review("P2", 2), _review("P2", 3)])

    rebuilt = ReviewLookup.build(source, cache_path)
    rows = rebuilt.read(["P1", "P2"], max_total=2)

    assert rebuilt.rebuilt is True
    assert rebuilt.review_count == 3
    assert len(rows) == 2
    assert [row.source_row for row in rows] == [1, 2]


def test_review_lookup_remains_prepared_when_only_source_mtime_changes(tmp_path: Path) -> None:
    source = tmp_path / "reviews.jsonl"
    cache_path = tmp_path / "review_lookup.sqlite"
    _write_jsonl(source, [_review("P1", 1)])
    ReviewLookup.build(source, cache_path)

    stat = source.stat()
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    prepared = ReviewLookup.open_prepared(source, cache_path)

    assert prepared.rebuilt is False
    assert prepared.review_count == 1


def test_review_lookup_requires_preparation_when_cache_is_missing(tmp_path: Path) -> None:
    source = tmp_path / "reviews.jsonl"
    _write_jsonl(source, [_review("P1", 1)])

    with pytest.raises(DataPreparationRequiredError, match="review lookup cache is missing"):
        ReviewLookup.open_prepared(source, tmp_path / "review_lookup.sqlite")


def test_review_lookup_is_stale_when_same_size_source_content_changes(tmp_path: Path) -> None:
    source = tmp_path / "reviews.jsonl"
    cache_path = tmp_path / "review_lookup.sqlite"
    _write_jsonl(source, [_review("P1", 1)])
    ReviewLookup.build(source, cache_path)

    source.write_bytes(source.read_bytes().replace(b"Original", b"original", 1))

    with pytest.raises(DataPreparationRequiredError, match="review lookup cache is stale"):
        ReviewLookup.open_prepared(source, cache_path)
