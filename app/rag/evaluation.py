from __future__ import annotations

import json
import random
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.core.enums import KnowledgeType
from app.rag.chroma import ChromaKnowledgeStore
from app.rag.reranker import Reranker, RerankSummary

RANDOM_SEED = 20260715


@dataclass(slots=True)
class GoldQuery:
    query_id: str
    collection: str
    knowledge_type: str
    query: str
    filters: dict[str, Any]
    expected: dict[str, list[str]]
    topic: str
    source_document_id: str
    leakage_flags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class QueryDetail:
    query_id: str
    query: str
    collection: str
    filters: dict[str, Any]
    expected: dict[str, list[str]]
    retrieved_ids: list[str]
    retrieved_expected_values: list[str]
    ranks: list[int]
    scores: list[float]
    vector_scores: list[float]
    rerank_scores: list[float | None]
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    reciprocal_rank: float
    latency_ms: float
    vector_latency_ms: float
    rerank_latency_ms: float
    duplicate_count: int
    metadata_filter_ok: bool
    empty: bool
    rerank_used: bool
    rerank_fallback: bool
    error: str | None = None


@dataclass(slots=True)
class EvaluationMetrics:
    collection: str
    mode: str
    query_count: int
    failed_query_count: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr: float
    empty_retrieval_rate: float
    duplicate_result_rate: float
    metadata_filter_accuracy: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    rerank_used_count: int = 0
    rerank_fallback_count: int = 0
    rerank_api_error_count: int = 0
    avg_rerank_latency_ms: float = 0.0
    rerank_model: str | None = None


def build_gold_dataset(store: ChromaKnowledgeStore, output_path: Path, *, per_collection: int = 200) -> list[GoldQuery]:
    rng = random.Random(RANDOM_SEED)
    product = _build_product_gold(store, rng, per_collection)
    review = _build_review_gold(store, rng, per_collection)
    dataset = product + review
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for item in dataset:
            handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
    return dataset


def load_gold_dataset(path: Path) -> list[GoldQuery]:
    records: list[GoldQuery] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                payload = json.loads(line)
                records.append(GoldQuery(**payload))
    return records


def evaluate_dataset(
    store: ChromaKnowledgeStore,
    dataset: list[GoldQuery],
    *,
    mode: str,
    output_dir: Path,
    top_k: int = 5,
    fetch_k: int = 30,
    reranker: Reranker | None = None,
    concurrency: int = 1,
) -> list[EvaluationMetrics]:
    output_dir.mkdir(parents=True, exist_ok=True)
    query_embeddings = _embed_queries(store, dataset)
    worker_count = max(1, concurrency)
    if worker_count == 1:
        details = [
            _evaluate_query(
                store,
                query,
                mode=mode,
                top_k=top_k,
                fetch_k=fetch_k,
                reranker=reranker,
                query_embedding=query_embeddings.get(query.query_id),
            )
            for query in dataset
        ]
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            details = list(
                executor.map(
                    lambda query: _evaluate_query(
                        store,
                        query,
                        mode=mode,
                        top_k=top_k,
                        fetch_k=fetch_k,
                        reranker=reranker,
                        query_embedding=query_embeddings.get(query.query_id),
                    ),
                    dataset,
                )
            )
    metrics = [
        _metrics_for(collection, mode, details, reranker)
        for collection in sorted({q.collection for q in dataset})
    ]
    _write_outputs(metrics, details, output_dir)
    return metrics


def write_comparison(
    vector_metrics: list[EvaluationMetrics],
    reranked_metrics: list[EvaluationMetrics],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    by_collection = {item.collection: item for item in vector_metrics}
    comparison: dict[str, Any] = {}
    lines = ["# RAG Evaluation Comparison", ""]
    for reranked in reranked_metrics:
        vector = by_collection[reranked.collection]
        latency_delta = reranked.avg_latency_ms - vector.avg_latency_ms
        comparison[reranked.collection] = {
            "vector_only": asdict(vector),
            "reranked": asdict(reranked),
            "hit_at_1_delta": reranked.hit_at_1 - vector.hit_at_1,
            "mrr_delta": reranked.mrr - vector.mrr,
            "hit_at_5_delta": reranked.hit_at_5 - vector.hit_at_5,
            "avg_latency_delta_ms": latency_delta,
            "p95_latency_delta_ms": reranked.p95_latency_ms - vector.p95_latency_ms,
            "reranker_fallback_rate": reranked.rerank_fallback_count / max(1, reranked.query_count),
            "default_enable_recommendation": (
                reranked.hit_at_1 > vector.hit_at_1
                and reranked.mrr >= vector.mrr
                and reranked.hit_at_5 >= vector.hit_at_5
                and latency_delta < 1000
            ),
        }
        lines.extend(
            [
                f"## {reranked.collection}",
                "",
                f"- Hit@1 delta: {comparison[reranked.collection]['hit_at_1_delta']:.4f}",
                f"- MRR delta: {comparison[reranked.collection]['mrr_delta']:.4f}",
                f"- Hit@5 delta: {comparison[reranked.collection]['hit_at_5_delta']:.4f}",
                f"- Avg latency delta ms: {latency_delta:.1f}",
                f"- P95 latency delta ms: {comparison[reranked.collection]['p95_latency_delta_ms']:.1f}",
                f"- Reranker fallback rate: {comparison[reranked.collection]['reranker_fallback_rate']:.4f}",
                f"- Recommend default enabled: {comparison[reranked.collection]['default_enable_recommendation']}",
                "",
            ]
        )
    (output_dir / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "comparison.md").write_text("\n".join(lines), encoding="utf-8")


def _build_product_gold(store: ChromaKnowledgeStore, rng: random.Random, limit: int) -> list[GoldQuery]:
    collection = store._collection(KnowledgeType.PRODUCT_KNOWLEDGE)  # type: ignore[attr-defined]
    raw = collection.get(limit=max(limit * 8, 2000), include=["documents", "metadatas"])
    candidates = _unique_by(raw, "parent_asin")
    rng.shuffle(candidates)
    templates = [
        ("function", "Which pet supply product has these functions: {terms}?"),
        ("spec", "Find the product information about {terms} for a {category} item."),
        ("scenario", "Which product fits the use case {terms} in {category}?"),
        ("brand", "Find product knowledge for a {brand} item described by {terms}."),
        ("rating", "Find product metadata for a {category} item rated about {rating} stars with {terms}."),
    ]
    records: list[GoldQuery] = []
    for index, (document_id, document, metadata) in enumerate(candidates):
        if len(records) >= limit:
            break
        metadata = metadata or {}
        parent_asin = str(metadata.get("parent_asin") or "")
        product_id = str(metadata.get("product_id") or "")
        if not parent_asin or not product_id:
            continue
        topic, template = templates[index % len(templates)]
        terms = _keywords(
            document,
            metadata,
            forbidden=[metadata.get("product_name"), parent_asin, product_id],
            count=5,
        )
        if len(terms) < 2:
            continue
        query = template.format(
            terms=", ".join(terms),
            category=str(metadata.get("category") or "pet supplies"),
            brand=str(metadata.get("brand") or "unknown brand"),
            rating=str(metadata.get("rating") or "unknown"),
        )
        filters = _product_filter(metadata, index)
        records.append(
            _gold(
                query_id=f"PK-{len(records) + 1:04d}",
                knowledge_type=KnowledgeType.PRODUCT_KNOWLEDGE,
                query=query,
                filters=filters,
                expected={
                    "document_id": [str(document_id)],
                    "parent_asin": [parent_asin],
                    "product_id": [product_id],
                },
                topic=topic,
                source_document_id=str(document_id),
                source_text=document or "",
                metadata=metadata,
            )
        )
    return records


def _build_review_gold(store: ChromaKnowledgeStore, rng: random.Random, limit: int) -> list[GoldQuery]:
    collection = store._collection(KnowledgeType.REVIEW_INSIGHT)  # type: ignore[attr-defined]
    raw = collection.get(limit=max(limit * 10, 3000), include=["documents", "metadatas"])
    candidates = _unique_by(raw, "review_id")
    rng.shuffle(candidates)
    templates = [
        ("durability", "Find a customer review about durability or item failure: {terms}."),
        ("size", "Find a customer review about size, fit, or dimensions: {terms}."),
        ("cleaning", "Find a customer review about cleaning, mess, or maintenance: {terms}."),
        ("odor", "Find a customer review mentioning smell, odor, or material concerns: {terms}."),
        ("pet_acceptance", "Find a customer review about whether the pet accepted or used the product: {terms}."),
        ("installation", "Find a customer review about setup, assembly, sticking, or instructions: {terms}."),
        ("positive", "Find a positive verified customer experience with {terms}."),
        ("complaint", "Find a low rating complaint that mentions {terms}."),
    ]
    records: list[GoldQuery] = []
    for index, (document_id, document, metadata) in enumerate(candidates):
        if len(records) >= limit:
            break
        metadata = metadata or {}
        review_id = str(metadata.get("review_id") or "")
        parent_asin = str(metadata.get("parent_asin") or "")
        product_id = str(metadata.get("product_id") or "")
        asin = str(metadata.get("asin") or "")
        if not review_id or not parent_asin or not product_id:
            continue
        topic, template = templates[index % len(templates)]
        terms = _keywords(
            document,
            metadata,
            forbidden=[metadata.get("review_title"), review_id, parent_asin, asin],
            count=5,
        )
        if len(terms) < 2:
            continue
        query = template.format(terms=", ".join(terms))
        filters = _review_filter(metadata, index)
        records.append(
            _gold(
                query_id=f"RI-{len(records) + 1:04d}",
                knowledge_type=KnowledgeType.REVIEW_INSIGHT,
                query=query,
                filters=filters,
                expected={
                    "document_id": [str(document_id)],
                    "review_id": [review_id],
                    "parent_asin": [parent_asin],
                    "product_id": [product_id],
                    "asin": [asin] if asin else [],
                },
                topic=topic,
                source_document_id=str(document_id),
                source_text=document or "",
                metadata=metadata,
            )
        )
    return records


def _evaluate_query(
    store: ChromaKnowledgeStore,
    query: GoldQuery,
    *,
    mode: str,
    top_k: int,
    fetch_k: int,
    reranker: Reranker | None,
    query_embedding: list[float] | None,
) -> QueryDetail:
    started = time.perf_counter()
    vector_started = time.perf_counter()
    rerank_summary = RerankSummary()
    try:
        knowledge_type = KnowledgeType(query.knowledge_type)
        collection = store._collection(knowledge_type)  # type: ignore[attr-defined]
        query_args: dict[str, Any] = {
            "n_results": min(fetch_k, collection.count()),
            "where": query.filters or None,
            "include": ["documents", "metadatas", "distances"],
        }
        if query_embedding is None:
            query_args["query_texts"] = [query.query]
        else:
            query_args["query_embeddings"] = [query_embedding]
        result = collection.query(**query_args)
        vector_latency_ms = (time.perf_counter() - vector_started) * 1000
        items = _query_items(result)
        if mode == "reranked" and reranker is not None and items:
            rerank_started = time.perf_counter()
            items, rerank_summary = reranker.rerank(query.query, items, top_n=top_k)
            rerank_latency_ms = (time.perf_counter() - rerank_started) * 1000
        else:
            rerank_latency_ms = 0.0
        items = items[:top_k]
        ids = [str(item["id"]) for item in items]
        expected_values = [_expected_value(item["metadata"], query) for item in items]
        ranks = _matching_ranks(items, query)
        duplicate_count = len(ids) - len(set(ids))
        rr = 1 / ranks[0] if ranks else 0.0
        return QueryDetail(
            query_id=query.query_id,
            query=query.query,
            collection=query.collection,
            filters=query.filters,
            expected=query.expected,
            retrieved_ids=ids,
            retrieved_expected_values=expected_values,
            ranks=ranks,
            scores=[float(item["score"]) for item in items],
            vector_scores=[float(item["vector_score"]) for item in items],
            rerank_scores=[item.get("rerank_score") for item in items],
            hit_at_1=bool(ranks and ranks[0] <= 1),
            hit_at_3=bool(ranks and ranks[0] <= 3),
            hit_at_5=bool(ranks and ranks[0] <= 5),
            reciprocal_rank=rr,
            latency_ms=(time.perf_counter() - started) * 1000,
            vector_latency_ms=vector_latency_ms,
            rerank_latency_ms=rerank_latency_ms,
            duplicate_count=duplicate_count,
            metadata_filter_ok=all(_matches_filter(item["metadata"], query.filters) for item in items),
            empty=not items,
            rerank_used=rerank_summary.used,
            rerank_fallback=rerank_summary.fallback,
            error=rerank_summary.error,
        )
    except Exception as exc:
        return QueryDetail(
            query_id=query.query_id,
            query=query.query,
            collection=query.collection,
            filters=query.filters,
            expected=query.expected,
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
            latency_ms=(time.perf_counter() - started) * 1000,
            vector_latency_ms=0.0,
            rerank_latency_ms=0.0,
            duplicate_count=0,
            metadata_filter_ok=False,
            empty=True,
            rerank_used=False,
            rerank_fallback=False,
            error=str(exc),
        )


def _metrics_for(
    collection: str,
    mode: str,
    details: list[QueryDetail],
    reranker: Reranker | None,
) -> EvaluationMetrics:
    selected = [item for item in details if item.collection == collection]
    count = len(selected)
    latencies = [item.latency_ms for item in selected]
    return EvaluationMetrics(
        collection=collection,
        mode=mode,
        query_count=count,
        failed_query_count=sum(1 for item in selected if item.error and not item.rerank_fallback),
        hit_at_1=_rate(item.hit_at_1 for item in selected),
        hit_at_3=_rate(item.hit_at_3 for item in selected),
        hit_at_5=_rate(item.hit_at_5 for item in selected),
        mrr=sum(item.reciprocal_rank for item in selected) / max(1, count),
        empty_retrieval_rate=_rate(item.empty for item in selected),
        duplicate_result_rate=sum(item.duplicate_count for item in selected) / max(1, count * 5),
        metadata_filter_accuracy=_rate(item.metadata_filter_ok for item in selected),
        avg_latency_ms=statistics.fmean(latencies) if latencies else 0.0,
        p50_latency_ms=_percentile(latencies, 0.50),
        p95_latency_ms=_percentile(latencies, 0.95),
        p99_latency_ms=_percentile(latencies, 0.99),
        rerank_used_count=sum(1 for item in selected if item.rerank_used),
        rerank_fallback_count=sum(1 for item in selected if item.rerank_fallback),
        rerank_api_error_count=sum(1 for item in selected if item.rerank_fallback and item.error),
        avg_rerank_latency_ms=statistics.fmean([item.rerank_latency_ms for item in selected]) if selected else 0.0,
        rerank_model=reranker.model_name if reranker else None,
    )


def _embed_queries(store: ChromaKnowledgeStore, dataset: list[GoldQuery]) -> dict[str, list[float]]:
    texts = [item.query for item in dataset]
    if not texts:
        return {}
    embedding_function = store.embedding_function
    if hasattr(embedding_function, "embed_documents"):
        embeddings = embedding_function.embed_documents(texts)
    elif hasattr(embedding_function, "embed_query"):
        embeddings = embedding_function.embed_query(texts)
    else:
        embeddings = embedding_function(texts)
    return {item.query_id: list(embedding) for item, embedding in zip(dataset, embeddings, strict=True)}


def _write_outputs(metrics: list[EvaluationMetrics], details: list[QueryDetail], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rag_evaluation.json").write_text(
        json.dumps([asdict(item) for item in metrics], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (output_dir / "rag_evaluation_details.jsonl").open("w", encoding="utf-8") as handle:
        for item in details:
            handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
    lines = ["# RAG Evaluation", ""]
    for item in metrics:
        lines.extend(
            [
                f"## {item.collection}",
                "",
                f"- mode: {item.mode}",
                f"- query_count: {item.query_count}",
                f"- failed_query_count: {item.failed_query_count}",
                f"- Hit@1: {item.hit_at_1:.4f}",
                f"- Hit@3: {item.hit_at_3:.4f}",
                f"- Hit@5: {item.hit_at_5:.4f}",
                f"- MRR: {item.mrr:.4f}",
                f"- Empty Retrieval Rate: {item.empty_retrieval_rate:.4f}",
                f"- Duplicate Result Rate: {item.duplicate_result_rate:.4f}",
                f"- Metadata Filter Accuracy: {item.metadata_filter_accuracy:.4f}",
                f"- Avg Latency Ms: {item.avg_latency_ms:.1f}",
                f"- P50 Latency Ms: {item.p50_latency_ms:.1f}",
                f"- P95 Latency Ms: {item.p95_latency_ms:.1f}",
                f"- P99 Latency Ms: {item.p99_latency_ms:.1f}",
                f"- Rerank Used Count: {item.rerank_used_count}",
                f"- Rerank Fallback Count: {item.rerank_fallback_count}",
                f"- Rerank API Error Count: {item.rerank_api_error_count}",
                f"- Avg Rerank Latency Ms: {item.avg_rerank_latency_ms:.1f}",
                "",
            ]
        )
    (output_dir / "rag_evaluation.md").write_text("\n".join(lines), encoding="utf-8")


def _unique_by(raw: dict[str, Any], metadata_key: str) -> list[tuple[str, str, dict[str, Any]]]:
    seen: set[str] = set()
    selected: list[tuple[str, str, dict[str, Any]]] = []
    for item_id, document, metadata in zip(
        raw.get("ids", []),
        raw.get("documents", []),
        raw.get("metadatas", []),
        strict=False,
    ):
        metadata = metadata or {}
        key = str(metadata.get(metadata_key) or item_id)
        if not key or key in seen:
            continue
        seen.add(key)
        selected.append((str(item_id), str(document or ""), metadata))
    return selected


def _gold(
    *,
    query_id: str,
    knowledge_type: KnowledgeType,
    query: str,
    filters: dict[str, Any],
    expected: dict[str, list[str]],
    topic: str,
    source_document_id: str,
    source_text: str,
    metadata: dict[str, Any],
) -> GoldQuery:
    flags = _leakage_flags(query, source_text, metadata)
    return GoldQuery(
        query_id=query_id,
        collection=knowledge_type.value,
        knowledge_type=knowledge_type.value,
        query=query,
        filters=filters,
        expected=expected,
        topic=topic,
        source_document_id=source_document_id,
        leakage_flags=flags,
    )


def _keywords(document: str, metadata: dict[str, Any], *, forbidden: list[Any], count: int) -> list[str]:
    text = re.sub(r"Rating:\s*\d+(\.\d+)?", " ", document or "", flags=re.I)
    forbidden_text = " ".join(str(item or "") for item in forbidden).lower()
    stop = {
        "product", "title", "rating", "from", "with", "this", "that", "have", "will", "your", "they", "them",
        "amazon", "review", "stars", "customer", "because", "about", "there", "their", "would", "were", "very",
        "just", "like", "used", "using", "really", "bought", "purchase", "great", "good",
    }
    terms: list[str] = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", text.lower()):
        if token in stop or token in forbidden_text:
            continue
        if token not in terms:
            terms.append(token)
        if len(terms) >= count:
            break
    category = str(metadata.get("category") or "").lower()
    if category and category not in " ".join(terms):
        terms.append(category)
    return terms[:count]


def _product_filter(metadata: dict[str, Any], index: int) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = [{"data_origin": "real"}, {"is_demo": False}]
    if index % 4 == 0:
        clauses.append({"product_id": metadata.get("product_id")})
    elif index % 4 == 1:
        clauses.append({"parent_asin": metadata.get("parent_asin")})
    elif index % 4 == 2 and metadata.get("category"):
        clauses.append({"category": metadata.get("category")})
    return _and(clauses)


def _review_filter(metadata: dict[str, Any], index: int) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = [{"data_origin": "real"}, {"is_demo": False}]
    if index % 6 == 0:
        clauses.append({"product_id": metadata.get("product_id")})
    elif index % 6 == 1:
        clauses.append({"parent_asin": metadata.get("parent_asin")})
    elif index % 6 == 2 and metadata.get("asin"):
        clauses.append({"asin": metadata.get("asin")})
    elif index % 6 == 3:
        rating = float(metadata.get("rating") or 0)
        clauses.append({"rating": {"$gte": max(1, rating - 0.5)}})
        clauses.append({"rating": {"$lte": min(5, rating + 0.5)}})
    elif index % 6 == 4:
        clauses.append({"verified_purchase": bool(metadata.get("verified_purchase"))})
    return _and(clauses)


def _and(clauses: list[dict[str, Any]]) -> dict[str, Any]:
    cleaned = [{k: v for k, v in clause.items() if v not in (None, "")} for clause in clauses]
    cleaned = [clause for clause in cleaned if clause]
    if len(cleaned) == 1:
        return cleaned[0]
    return {"$and": cleaned}


def _query_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for item_id, document, metadata, distance in zip(
        result.get("ids", [[]])[0],
        result.get("documents", [[]])[0],
        result.get("metadatas", [[]])[0],
        result.get("distances", [[]])[0],
        strict=False,
    ):
        score = max(0.0, 1.0 - float(distance or 0.0))
        items.append(
            {
                "id": item_id,
                "document": document or "",
                "metadata": metadata or {},
                "score": score,
                "vector_score": score,
                "rerank_score": None,
            }
        )
    return items


def _matching_ranks(items: list[dict[str, Any]], query: GoldQuery) -> list[int]:
    ranks: list[int] = []
    for index, item in enumerate(items, start=1):
        if _matches_expected(str(item["id"]), item["metadata"], query.expected):
            ranks.append(index)
    return ranks


def _matches_expected(item_id: str, metadata: dict[str, Any], expected: dict[str, list[str]]) -> bool:
    for key, values in expected.items():
        if not values:
            continue
        actual = item_id if key == "document_id" else str(metadata.get(key) or "")
        if actual in {str(value) for value in values if value}:
            return True
    return False


def _expected_value(metadata: dict[str, Any], query: GoldQuery) -> str:
    for key in ("review_id", "parent_asin", "product_id", "asin"):
        if query.expected.get(key):
            return str(metadata.get(key) or "")
    return str(metadata.get("document_id") or "")


def _matches_filter(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
    if not filters:
        return True
    if "$and" in filters:
        return all(_matches_filter(metadata, clause) for clause in filters["$and"])
    for key, expected in filters.items():
        actual = metadata.get(key)
        if isinstance(expected, dict):
            if "$gte" in expected and not (float(actual) >= float(expected["$gte"])):
                return False
            if "$lte" in expected and not (float(actual) <= float(expected["$lte"])):
                return False
        elif actual != expected:
            return False
    return True


def _leakage_flags(query: str, source_text: str, metadata: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    normalized_query = " ".join(query.lower().split())
    normalized_source = " ".join((source_text or "").lower().split())
    if normalized_query and normalized_query == normalized_source:
        flags.append("query_equals_full_source")
    for key in ("product_name", "review_title"):
        value = " ".join(str(metadata.get(key) or "").lower().split())
        if value and normalized_query == value:
            flags.append(f"query_equals_{key}")
    for key in ("parent_asin", "asin", "review_id", "product_id"):
        value = str(metadata.get(key) or "")
        if value and value.lower() in normalized_query:
            flags.append(f"query_leaks_{key}")
    return flags


def _rate(values: Any) -> float:
    values = list(values)
    return sum(1 for value in values if value) / max(1, len(values))


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[index]
