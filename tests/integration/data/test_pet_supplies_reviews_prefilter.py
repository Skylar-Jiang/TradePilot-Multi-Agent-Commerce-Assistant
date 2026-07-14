import json
from pathlib import Path

from scripts.domain_imports.prefilter_pet_supplies_reviews import (
    load_product_parent_asins,
    prefilter_pet_supplies_reviews,
)


def test_load_product_parent_asins_reads_parent_asins_from_filtered_products(tmp_path: Path) -> None:
    product_input_path = tmp_path / "products.jsonl"
    product_input_path.write_text(
        "\n".join(
            [
                json.dumps({"parent_asin": "PARENT-1", "title": "Product 1"}),
                json.dumps({"parent_asin": "PARENT-2", "title": "Product 2"}),
                json.dumps({"parent_asin": "  PARENT-1  ", "title": "Duplicate Product 1"}),
                "{not valid json}",
            ]
        ),
        encoding="utf-8",
    )

    parent_asins = load_product_parent_asins(product_input_path)

    assert parent_asins == {"PARENT-1", "PARENT-2"}


def test_prefilter_pet_supplies_reviews_keeps_only_reviews_for_prefiltered_products(tmp_path: Path) -> None:
    product_input_path = tmp_path / "products.jsonl"
    review_input_path = tmp_path / "reviews.jsonl"
    output_path = tmp_path / "filtered_reviews.jsonl"
    product_input_path.write_text(
        "\n".join(
            [
                json.dumps({"parent_asin": "PARENT-1", "title": "Product 1"}),
                json.dumps({"parent_asin": "PARENT-2", "title": "Product 2"}),
            ]
        ),
        encoding="utf-8",
    )
    review_input_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "parent_asin": "PARENT-1",
                        "asin": "ASIN-1",
                        "rating": 5.0,
                        "title": "Great",
                        "text": "My dog loves it.",
                        "verified_purchase": True,
                    }
                ),
                json.dumps(
                    {
                        "parent_asin": "PARENT-3",
                        "asin": "ASIN-2",
                        "rating": 4.0,
                        "title": "Wrong Product Set",
                        "text": "This should not be kept.",
                    }
                ),
                json.dumps(
                    {
                        "parent_asin": "PARENT-2",
                        "asin": "ASIN-3",
                        "rating": None,
                        "title": "Missing Rating",
                        "text": "This should be dropped.",
                    }
                ),
                json.dumps(
                    {
                        "parent_asin": "PARENT-2",
                        "asin": "ASIN-4",
                        "rating": 3.0,
                        "title": "   ",
                        "text": "This should be dropped.",
                    }
                ),
                json.dumps(
                    {
                        "parent_asin": "PARENT-2",
                        "asin": "ASIN-5",
                        "rating": 2.0,
                        "title": "Missing Text",
                        "text": "   ",
                    }
                ),
                json.dumps(
                    {
                        "parent_asin": "",
                        "asin": "ASIN-6",
                        "rating": 1.0,
                        "title": "Missing Parent",
                        "text": "This should be dropped.",
                    }
                ),
                "{not valid json}",
            ]
        ),
        encoding="utf-8",
    )

    summary = prefilter_pet_supplies_reviews(review_input_path, product_input_path, output_path)

    assert summary.product_parent_asins == 2
    assert summary.total == 7
    assert summary.kept == 1
    assert summary.dropped_not_in_product_set == 1
    assert summary.dropped_missing_rating == 1
    assert summary.dropped_missing_title == 1
    assert summary.dropped_missing_text == 1
    assert summary.dropped_missing_parent_asin == 1
    assert summary.dropped_invalid_json == 1

    kept_lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(kept_lines) == 1
    kept_record = json.loads(kept_lines[0])
    assert kept_record["parent_asin"] == "PARENT-1"
    assert kept_record["title"] == "Great"


def test_prefilter_pet_supplies_reviews_can_cap_reviews_per_parent(tmp_path: Path) -> None:
    product_input_path = tmp_path / "products.jsonl"
    review_input_path = tmp_path / "reviews.jsonl"
    output_path = tmp_path / "filtered_reviews.jsonl"
    product_input_path.write_text(json.dumps({"parent_asin": "PARENT-1", "title": "Product 1"}), encoding="utf-8")
    review_input_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "parent_asin": "PARENT-1",
                        "asin": f"ASIN-{index}",
                        "rating": 5.0,
                        "title": f"Review {index}",
                        "text": f"Body {index}",
                    }
                )
                for index in range(1, 5)
            ]
        ),
        encoding="utf-8",
    )

    summary = prefilter_pet_supplies_reviews(
        review_input_path,
        product_input_path,
        output_path,
        max_reviews_per_parent=2,
    )

    assert summary.total == 4
    assert summary.kept == 2
    assert summary.dropped_exceeds_max_reviews_per_parent == 2

    kept_records = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert [record["title"] for record in kept_records] == ["Review 1", "Review 2"]
