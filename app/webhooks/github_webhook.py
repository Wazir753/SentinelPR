"""GitHub webhook ingress for workflow_run CI failures."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.agent.graph import run_pipeline
from app.config import PROJECT_ROOT, settings
from app.events import store as event_store
from app.logging_config import log_stage
from app.webhooks.models import ParsedCIFailure, WebhookAck
from app.webhooks.parser import load_mock_payload, parse_workflow_run_failure, verify_github_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

TEST_REPO = PROJECT_ROOT / "test_repo"


async def _handle_workflow_run_payload(
    payload: dict,
    *,
    is_mock: bool,
    background_tasks: BackgroundTasks,
) -> WebhookAck:
    failure = parse_workflow_run_failure(payload, is_mock=is_mock)
    if failure is None:
        return WebhookAck(
            status="ignored",
            message="Payload received but not a completed workflow failure.",
        )

    event_store.record_failure(failure)
    log_stage(
        logger,
        "webhook_ingress",
        "CI failure event recorded",
        event_id=failure.event_id,
        repo=failure.repo_full_name,
        workflow_run_id=failure.workflow_run_id,
    )

    local_repo_path = str(TEST_REPO) if is_mock else None
    background_tasks.add_task(run_pipeline, failure, local_repo_path=local_repo_path)

    return WebhookAck(
        status="accepted",
        message="CI failure recorded; agent pipeline started.",
        failure=failure,
    )


@router.post("/github", response_model=WebhookAck)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> WebhookAck:
    body = await request.body()

    if settings.github_webhook_secret and not verify_github_signature(
        body, x_hub_signature_256, settings.github_webhook_secret
    ):
        log_stage(logger, "webhook_ingress", "Invalid webhook signature", result="rejected")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    log_stage(
        logger,
        "webhook_ingress",
        "GitHub webhook received",
        github_event=x_github_event,
        action=payload.get("action"),
    )

    if x_github_event != "workflow_run":
        return WebhookAck(
            status="ignored",
            message=f"Event type '{x_github_event}' is not handled.",
        )

    return await _handle_workflow_run_payload(payload, is_mock=False, background_tasks=background_tasks)


@router.post("/github/mock", response_model=WebhookAck)
async def github_webhook_mock(background_tasks: BackgroundTasks) -> WebhookAck:
    if not settings.is_development:
        raise HTTPException(status_code=403, detail="Mock endpoint disabled outside development")

    payload = load_mock_payload()
    log_stage(logger, "webhook_ingress", "Processing mock workflow_run failure payload")
    return await _handle_workflow_run_payload(payload, is_mock=True, background_tasks=background_tasks)


@router.get("/failures", response_model=list[ParsedCIFailure])
async def list_recent_failures(limit: int = 20) -> list[ParsedCIFailure]:
    return event_store.list_failures(limit=min(limit, 100))
