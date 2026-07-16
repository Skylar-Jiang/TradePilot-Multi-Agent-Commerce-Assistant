from __future__ import annotations

import logging
from time import perf_counter

HTTP_LOGGER_NAME = "tradepilot.http"


def configure_logging(level: str) -> None:
    """Configure application log levels without replacing server/test handlers."""
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger("tradepilot").setLevel(resolved_level)
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=resolved_level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )


def log_http_request(
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    started_at: float,
    error: Exception | None = None,
) -> None:
    """Write allow-listed request metadata; headers, query strings and bodies are excluded."""
    logging.getLogger(HTTP_LOGGER_NAME).info(
        "http_request_completed",
        extra={
            "event": "http_request_completed",
            "request_id": request_id,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round((perf_counter() - started_at) * 1000, 3),
            "error_type": type(error).__name__ if error is not None else None,
        },
    )
