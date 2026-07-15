import json
from pathlib import Path

from app.rag.evaluation import (
    EvaluationMetrics,
    GoldQuery,
    QueryDetail,
    _matches_filter,
    _matching_ranks,
    _metrics_for,
    _percentile,
    _write_outputs,
    write_comparison,
)


def test_matching_ranks_and_reciprocal_rank() -> None:
    query = GoldQuery(
        query_id="q1",
        collection="review_insight",
        knowledge_type="review_insight",
        query="durability issue",
        filters={},
        expected={"review_id": ["r2"]},
        topic="durability",
        source_document_id="d2",
    )
    ranks = _matching_ranks(
        [
            {"id": "d1", "metadata": {"review_id": "r1"}},
            {"id": "d2", "metadata": {"review_id": "r2"}},
        ],
        query,
    )
    assert ranks == [2]
    assert 1 / ranks[0] == 0.5


def test_metadata_filter_accuracy_with_range_and_and() -> None:
    filters = {"$and": [{"data_origin": "real"}, {"rating": {"$gte": 2.5}}, {"rating": {"$lte": 3.5}}]}
    assert _matches_filter({"data_origin": "real", "rating": 3.0}, filters)
    assert not _matches_filter({"data_origin": "real", "rating": 5.0}, filters)
    assert not _matches_filter({"data_origin": "demo", "rating": 3.0}, filters)


def test_metrics_count_empty_failures_and_duplicates() -> None:
    details = [
        QueryDetail(
            query_id="q1",
            query="a",
            collection="product_knowledge",
            filters={},
            expected={},
            retrieved_ids=["x", "x"],
            retrieved_expected_values=[],
            ranks=[1],
            scores=[0.9, 0.8],
            vector_scores=[0.9, 0.8],
            rerank_scores=[None, None],
            hit_at_1=True,
            hit_at_3=True,
            hit_at_5=True,
            reciprocal_rank=1.0,
            latency_ms=10.0,
            vector_latency_ms=9.0,
            rerank_latency_ms=0.0,
            duplicate_count=1,
            metadata_filter_ok=True,
            empty=False,
            rerank_used=False,
            rerank_fallback=False,
            error=None,
        ),
        QueryDetail(
            query_id="q2",
            query="b",
            collection="product_knowledge",
            filters={},
            expected={},
            retrieved_ids=[],
            retrieved_expected_values=[],
            ranks=[],
            scores=[],
            vector_scores=[],
            rerank_scores=[],
            hit_at_1=False,
            hit_at_3=False,
            hit_at_5=False,
            reciprocal_rank=0.0,
            latency_ms=20.0,
            vector_latency_ms=20.0,
            rerank_latency_ms=0.0,
            duplicate_count=0,
            metadata_filter_ok=False,
            empty=True,
            rerank_used=False,
            rerank_fallback=False,
            error="boom",
        ),
    ]
    metrics = _metrics_for("product_knowledge", "vector_only", details, None)
    assert metrics.query_count == 2
    assert metrics.failed_query_count == 1
    assert metrics.hit_at_1 == 0.5
    assert metrics.empty_retrieval_rate == 0.5
    assert metrics.duplicate_result_rate == 0.1
    assert metrics.metadata_filter_accuracy == 0.5
    assert metrics.mrr == 0.5


def test_percentile_uses_sorted_values() -> None:
    assert _percentile([30, 10, 20], 0.5) == 20


def test_reports_and_comparison_are_written(tmp_path: Path) -> None:
    metrics = [
        EvaluationMetrics(
            collection="product_knowledge",
            mode="vector_only",
            query_count=1,
            failed_query_count=0,
            hit_at_1=1,
            hit_at_3=1,
            hit_at_5=1,
            mrr=1,
            empty_retrieval_rate=0,
            duplicate_result_rate=0,
            metadata_filter_accuracy=1,
            avg_latency_ms=1,
            p50_latency_ms=1,
            p95_latency_ms=1,
            p99_latency_ms=1,
        )
    ]
    _write_outputs(metrics, [], tmp_path / "vector")
    assert (tmp_path / "vector" / "rag_evaluation.json").exists()
    assert (tmp_path / "vector" / "rag_evaluation.md").exists()
    assert (tmp_path / "vector" / "rag_evaluation_details.jsonl").exists()
    write_comparison(metrics, metrics, tmp_path)
    assert json.loads((tmp_path / "comparison.json").read_text(encoding="utf-8"))
    assert (tmp_path / "comparison.md").exists()
