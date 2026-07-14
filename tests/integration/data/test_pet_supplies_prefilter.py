import json
from pathlib import Path

from scripts.domain_imports.prefilter_pet_supplies import prefilter_pet_supplies


def test_prefilter_pet_supplies_drops_rows_that_cannot_support_import(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "filtered.jsonl"
    input_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "main_category": "Pet Supplies",
                        "title": "Valid Pet Product",
                        "price": 12.5,
                        "parent_asin": "PARENT-1",
                        "categories": ["Pet Supplies", "Dogs"],
                    }
                ),
                json.dumps(
                    {
                        "main_category": "Pet Supplies",
                        "title": "Missing Price",
                        "price": None,
                        "parent_asin": "PARENT-2",
                        "categories": ["Pet Supplies", "Cats"],
                    }
                ),
                json.dumps(
                    {
                        "main_category": "Baby",
                        "title": "Wrong Domain",
                        "price": 18.0,
                        "parent_asin": "PARENT-3",
                        "categories": ["Baby"],
                    }
                ),
                json.dumps(
                    {
                        "main_category": "Pet Supplies",
                        "title": "   ",
                        "price": 22.0,
                        "parent_asin": "PARENT-4",
                        "categories": ["Pet Supplies", "Fish & Aquatic Pets"],
                    }
                ),
                json.dumps(
                    {
                        "main_category": "Pet Supplies",
                        "title": "Missing Parent ASIN",
                        "price": 30.0,
                        "parent_asin": "",
                        "categories": ["Pet Supplies", "Dogs"],
                    }
                ),
                "{not valid json}",
            ]
        ),
        encoding="utf-8",
    )

    summary = prefilter_pet_supplies(input_path, output_path)

    assert summary.total == 6
    assert summary.kept == 1
    assert summary.dropped_missing_price == 1
    assert summary.dropped_non_pet_supplies == 1
    assert summary.dropped_missing_title == 1
    assert summary.dropped_missing_parent_asin == 1
    assert summary.dropped_invalid_json == 1

    kept_lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(kept_lines) == 1
    kept_record = json.loads(kept_lines[0])
    assert kept_record["title"] == "Valid Pet Product"
    assert kept_record["parent_asin"] == "PARENT-1"


def test_prefilter_pet_supplies_keeps_category_matches_even_if_main_category_is_dirty(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "filtered.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "main_category": "Amazon Home",
                "title": "Pet Bowl",
                "price": 19.99,
                "parent_asin": "PARENT-9",
                "categories": ["Pet Supplies", "Dogs", "Feeding & Watering Supplies"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = prefilter_pet_supplies(input_path, output_path)

    assert summary.total == 1
    assert summary.kept == 1
    assert summary.dropped_non_pet_supplies == 0
