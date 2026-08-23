"""Status API for pipeline events."""

from __future__ import annotations

from fastapi import APIRouter

from app.events import store as event_store

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status")
async def status(limit: int = 20):
    failures = event_store.list_failures(limit=min(limit, 100))
    pipelines = {p.event_id: p for p in event_store.list_pipelines(limit=100)}

    events = []
    for failure in failures:
        pipeline = pipelines.get(failure.event_id)
        events.append(
            {
                "event_id": failure.event_id,
                "repo": failure.repo_full_name,
                "head_sha": failure.head_sha,
                "workflow_run_id": failure.workflow_run_id,
                "workflow_url": failure.workflow_url,
                "received_at": failure.received_at.isoformat(),
                "pipeline_status": pipeline.status if pipeline else None,
                "outcome": pipeline.outcome if pipeline else None,
                "patch_attempts": pipeline.patch_attempts if pipeline else 0,
                "pr_url": pipeline.pr_url if pipeline else None,
                "issue_url": pipeline.issue_url if pipeline else None,
                "trace": pipeline.trace if pipeline else [],
            }
        )

    return {"phase": 2, "events": events}
