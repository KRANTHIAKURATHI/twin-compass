"""
Structured logging setup.

JSON-formatted logs correlated by request ID (FastAPI Backend Architecture
Blueprint Section 17: "Application logs" + "Security logs"). Kept minimal —
this is stdlib `logging` with a JSON formatter and a request-scoped
context var, not a heavyweight logging framework, since Module 1 doesn't
need anything more.
"""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

from app.core.config import get_settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if settings.LOG_JSON:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)

    # Quiet noisy third-party loggers at INFO in local dev.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("hpack").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_security_event(logger: logging.Logger, event: str, **fields: object) -> None:
    """Elevated-severity marker for auth failures, role-check denials, rate-limit
    triggers — per Backend Blueprint Section 17's "Security logs" category."""
    logger.warning(event, extra={"extra_fields": {"security_event": event, **fields}})
