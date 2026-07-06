"""Analysis cache and agent reasoning trace persistence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MEMORY_DIR = Path("memory")
CACHE_PATH = MEMORY_DIR / "analysis_cache.json"
TRACE_PATH = MEMORY_DIR / "agent_traces.jsonl"


def make_cache_key(agent: str, competitor: str, question: str, top_k: int) -> str:
    raw = json.dumps(
        {"agent": agent, "competitor": competitor, "question": question, "top_k": top_k},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def get_cached_result(key: str) -> dict[str, Any] | None:
    return load_cache().get(key)


def set_cached_result(key: str, value: dict[str, Any]) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    cache = load_cache()
    cache[key] = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "value": value,
    }
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def append_trace(entry: dict[str, Any]) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    trace = {"created_at": datetime.now(timezone.utc).isoformat(), **entry}
    with TRACE_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(trace, ensure_ascii=False) + "\n")


def read_traces(limit: int = 50) -> list[dict[str, Any]]:
    if not TRACE_PATH.exists():
        return []
    lines = TRACE_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines[-limit:]]


def clear_cache() -> dict[str, int]:
    count = len(load_cache())
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()
    return {"cleared": count}
