"""Status API placeholder — expanded in Phase 4."""

from __future__ import annotations

from fastapi import APIRouter

from app.events import store as event_store

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status")
async def status(limit: int = 20):
    failures = event_store.list_failures(limit=min(limit, 100))
    return {
        "phase": 1,
        "events": [
            {
                "event_id": f.event_id,
                "repo": f.repo_full_name,
                "head_sha": f.head_sha,
                "workflow_run_id": f.workflow_run_id,
                "workflow_url": f.workflow_url,
                "received_at": f.received_at.isoformat(),
                "outcome": None,
                "patch_attempts": 0,
            }
            for f in failures
        ],
    }
