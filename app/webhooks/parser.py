"""Parse and validate GitHub workflow_run webhook payloads."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.logging_config import log_stage
from app.webhooks.models import ParsedCIFailure, WorkflowRunEvent

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


def verify_github_signature(payload_body: bytes, signature_header: str | None, secret: str) -> bool:
    if not secret:
        return True
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def parse_workflow_run_failure(payload: dict, *, is_mock: bool = False) -> ParsedCIFailure | None:
    event = WorkflowRunEvent.model_validate(payload)

    if event.action != "completed":
        log_stage(logger, "webhook_ingress", "Ignoring non-completed workflow_run", action=event.action)
        return None

    run = event.workflow_run
    if run.conclusion != "failure":
        log_stage(
            logger,
            "webhook_ingress",
            "Ignoring workflow_run without failure conclusion",
            workflow_run_id=run.id,
            conclusion=run.conclusion,
            status=run.status,
        )
        return None

    repo = event.repository
    head_commit = run.head_commit or {}
    event_id = f"wf-{run.id}-{run.head_sha[:8]}"

    failure = ParsedCIFailure(
        event_id=event_id,
        received_at=datetime.now(timezone.utc),
        action=event.action,
        workflow_run_id=run.id,
        workflow_name=run.name,
        run_number=run.run_number,
        conclusion=run.conclusion,
        head_branch=run.head_branch,
        head_sha=run.head_sha,
        repo_full_name=repo.get("full_name", "unknown/unknown"),
        repo_clone_url=repo.get("clone_url", ""),
        workflow_url=run.html_url,
        commit_message=head_commit.get("message"),
        sender_login=event.sender.get("login"),
        is_mock=is_mock,
        raw_payload=payload,
    )

    log_stage(
        logger,
        "webhook_ingress",
        "CI failure parsed",
        event_id=failure.event_id,
        repo=failure.repo_full_name,
        workflow=failure.workflow_name,
        run_number=failure.run_number,
        head_sha=failure.head_sha,
        is_mock=is_mock,
    )
    return failure


def load_mock_payload() -> dict:
    fixture_path = FIXTURES_DIR / "mock_workflow_run_failure.json"
    with fixture_path.open(encoding="utf-8") as handle:
        return json.load(handle)
