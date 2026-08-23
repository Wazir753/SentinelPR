"""In-memory store for CI failure events and pipeline runs."""

from __future__ import annotations

from threading import Lock

from app.events.models import PipelineRecord
from app.webhooks.models import ParsedCIFailure

_lock = Lock()
_events: list[ParsedCIFailure] = []
_pipelines: dict[str, PipelineRecord] = {}
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


def record_pipeline(record: PipelineRecord) -> None:
    with _lock:
        _pipelines[record.event_id] = record


def update_pipeline(record: PipelineRecord) -> None:
    with _lock:
        _pipelines[record.event_id] = record


def get_pipeline(event_id: str) -> PipelineRecord | None:
    with _lock:
        return _pipelines.get(event_id)


def list_pipelines(limit: int = 50) -> list[PipelineRecord]:
    with _lock:
        records = list(_pipelines.values())
    records.sort(key=lambda r: r.event_id, reverse=True)
    return records[:limit]


def clear_failures() -> None:
    with _lock:
        _events.clear()


def clear_pipelines() -> None:
    with _lock:
        _pipelines.clear()


def clear_all() -> None:
    with _lock:
        _events.clear()
        _pipelines.clear()
