"""GitHub webhook ingress routes."""

import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.models.webhook import ParsedCIFailure, WebhookAck
from app.services import failure_store
from app.services.webhook_parser import load_mock_payload, parse_workflow_run_failure, verify_github_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _handle_workflow_run_payload(payload: dict, *, is_mock: bool) -> WebhookAck:
    failure = parse_workflow_run_failure(payload, is_mock=is_mock)
    if failure is None:
        return WebhookAck(
            status="ignored",
            message="Payload received but not a completed workflow failure.",
        )

    failure_store.record_failure(failure)
    logger.info(
        "Recorded CI failure event_id=%s repo=%s",
        failure.event_id,
        failure.repo_full_name,
    )

    # Step 2+ will enqueue the LangGraph pipeline here.
    return WebhookAck(
        status="accepted",
        message="CI failure recorded. Agent pipeline not yet wired (step 1).",
        failure=failure,
    )


@router.post("/github", response_model=WebhookAck)
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> WebhookAck:
    """
    Receive GitHub webhooks.

    For MVP step 1, only `workflow_run` events with conclusion=failure are processed.
    """
    body = await request.body()

    if settings.github_webhook_secret and not verify_github_signature(
        body, x_hub_signature_256, settings.github_webhook_secret
    ):
        logger.warning("Invalid GitHub webhook signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    logger.info("GitHub webhook received: event=%s action=%s", x_github_event, payload.get("action"))

    if x_github_event != "workflow_run":
        return WebhookAck(
            status="ignored",
            message=f"Event type '{x_github_event}' is not handled yet.",
        )

    return await _handle_workflow_run_payload(payload, is_mock=False)


@router.post("/github/mock", response_model=WebhookAck)
async def github_webhook_mock() -> WebhookAck:
    """
    Trigger the webhook handler with a bundled fake CI failure payload.

    Use this to test end-to-end wiring without real GitHub Actions.
    Only available when APP_ENV=development.
    """
    if not settings.is_development:
        raise HTTPException(status_code=403, detail="Mock endpoint disabled outside development")

    payload = load_mock_payload()
    logger.info("Processing mock workflow_run failure payload")
    return await _handle_workflow_run_payload(payload, is_mock=True)


@router.get("/failures", response_model=list[ParsedCIFailure])
async def list_recent_failures(limit: int = 20) -> list[ParsedCIFailure]:
    """List recently recorded CI failures (in-memory, for step 1 testing)."""
    return failure_store.list_failures(limit=min(limit, 100))
