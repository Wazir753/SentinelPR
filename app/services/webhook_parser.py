"""Parse and validate GitHub workflow_run webhook payloads."""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from app.models.webhook import ParsedCIFailure, WorkflowRunEvent

logger = logging.getLogger(__name__)


def verify_github_signature(payload_body: bytes, signature_header: str | None, secret: str) -> bool:
    """Verify X-Hub-Signature-256 when a webhook secret is configured."""
    if not secret:
        return True
    if not signature_header:
        return False

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def parse_workflow_run_failure(payload: dict, *, is_mock: bool = False) -> ParsedCIFailure | None:
    """
    Parse a workflow_run webhook payload.

    Returns a ParsedCIFailure only when the run has failed; otherwise None.
    """
    event = WorkflowRunEvent.model_validate(payload)

    if event.action not in {"completed", "requested"}:
        logger.info("Ignoring workflow_run action=%s", event.action)
        return None

    run = event.workflow_run
    if run.conclusion != "failure":
        logger.info(
            "Ignoring workflow_run id=%s conclusion=%s status=%s",
            run.id,
            run.conclusion,
            run.status,
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

    logger.info(
        "CI failure parsed: repo=%s workflow=%s run=#%s sha=%s mock=%s",
        failure.repo_full_name,
        failure.workflow_name,
        failure.run_number,
        failure.head_sha[:8],
        is_mock,
    )
    return failure


def load_mock_payload() -> dict:
    """Load the bundled mock workflow_run failure payload."""
    from pathlib import Path

    fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "mock_workflow_run_failure.json"
    with fixture_path.open(encoding="utf-8") as f:
        return json.load(f)
