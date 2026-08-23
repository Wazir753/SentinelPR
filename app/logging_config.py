"""Structured JSON logging for SentinelPR pipeline stages."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log line for grep-friendly tracing."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "structured", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(handler)


def log_stage(
    logger: logging.Logger,
    stage: str,
    message: str,
    *,
    event_id: str | None = None,
    **fields: Any,
) -> None:
    """Log a pipeline stage event with consistent structured fields."""
    structured: dict[str, Any] = {"stage": stage, **fields}
    if event_id:
        structured["event_id"] = event_id
    logger.info(message, extra={"structured": structured})
