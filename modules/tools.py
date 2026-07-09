"""Reusable tools for competitor intelligence agents."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from modules.data_loader import IntelligenceRecord, load_csv, save_records_csv
from modules.rag_chain import SimpleRAGIndex, build_project_index

_PROJECT_INDEX_CACHE: SimpleRAGIndex | None = None


def get_project_index() -> SimpleRAGIndex:
    global _PROJECT_INDEX_CACHE
    if _PROJECT_INDEX_CACHE is None:
        _PROJECT_INDEX_CACHE = SimpleRAGIndex.load()
    return _PROJECT_INDEX_CACHE


def ingest_csv_tool(path: str, output_path: str = "data/processed/intelligence_records.csv") -> dict[str, Any]:
    global _PROJECT_INDEX_CACHE
    records = load_csv(path)
    saved_path = save_records_csv(records, output_path)
    _PROJECT_INDEX_CACHE = build_project_index()
    return {"count": len(records), "output_path": str(saved_path)}


def add_manual_record_tool(
    title: str,
    content: str,
    source_url: str,
    competitor: str = "",
    dimension: str = "general",
    output_path: str = "data/raw/manual_records.csv",
) -> dict[str, Any]:
    global _PROJECT_INDEX_CACHE
    record = IntelligenceRecord(
        title=title,
        content=content,
        source_url=source_url,
        source_type="manual",
        competitor=competitor,
        dimension=dimension,
    )
    existing = []
    if Path(output_path).exists():
        existing = load_csv(output_path)
    records = existing + [record]
    saved_path = save_records_csv(records, output_path)
    _PROJECT_INDEX_CACHE = build_project_index()
    return {"record": asdict(record), "output_path": str(saved_path)}


def retrieve_evidence_tool(
    query: str,
    dimension: str | None = None,
    top_k: int = 5,
    competitor: str | None = None,
) -> list[dict[str, Any]]:
    index = get_project_index()
    return [
        asdict(chunk)
        for chunk in index.search(query=query, top_k=top_k, dimension=dimension, competitor=competitor)
    ]
