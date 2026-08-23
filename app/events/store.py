"""In-memory store for CI failure events (Phase 4 will expose via /status)."""

from __future__ import annotations

from threading import Lock

from app.webhooks.models import ParsedCIFailure

_lock = Lock()
_events: list[ParsedCIFailure] = []
_MAX_EVENTS = 200


def record_failure(event: ParsedCIFailure) -> None:
    with _lock:
        _events.insert(0, event)
        del _events[_MAX_EVENTS:]


def list_failures(limit: int = 50) -> list[ParsedCIFailure]:
    with _lock:
        return list(_events[:limit])


def get_failure(event_id: str) -> ParsedCIFailure | None:
    with _lock:
        for event in _events:
            if event.event_id == event_id:
                return event
    return None


def clear_failures() -> None:
    with _lock:
        _events.clear()
