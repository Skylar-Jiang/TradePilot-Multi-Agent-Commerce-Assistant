"""Background polling scheduler for incremental collection."""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

from modules.source_manager import append_collection_log, run_collection_job

_started = False
_lock = threading.Lock()


def scheduler_enabled() -> bool:
    return os.getenv("COLLECTION_SCHEDULER_ENABLED", "true").lower() in {"1", "true", "yes", "on"}


def start_background_collector() -> bool:
    global _started
    if not scheduler_enabled():
        return False
    with _lock:
        if _started:
            return True
        thread = threading.Thread(target=_collector_loop, name="collection-scheduler", daemon=True)
        thread.start()
        _started = True
        return True


def _collector_loop() -> None:
    poll_seconds = int(os.getenv("COLLECTION_POLL_SECONDS", "300"))
    while True:
        try:
            result = run_collection_job(force=False, use_llm_filter=True)
            if result.get("collected") or result.get("errors"):
                append_collection_log(
                    {
                        "source_id": "__scheduler__",
                        "source_type": "scheduler",
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "result": result,
                    }
                )
        except Exception as exc:
            append_collection_log(
                {
                    "source_id": "__scheduler__",
                    "source_type": "scheduler_error",
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                }
            )
        time.sleep(max(poll_seconds, 30))
