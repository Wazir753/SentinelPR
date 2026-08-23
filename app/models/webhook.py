"""Pydantic models for GitHub webhook payloads."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowConclusion(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"
    NEUTRAL = "neutral"
    STALE = "stale"


class WorkflowRunPayload(BaseModel):
    id: int
    name: str
    head_branch: str
    head_sha: str
    run_number: int
    event: str
    status: str
    conclusion: str | None = None
    html_url: str
    repository: dict[str, Any]
    head_commit: dict[str, Any] | None = None


class WorkflowRunEvent(BaseModel):
    action: str
    workflow_run: WorkflowRunPayload
    repository: dict[str, Any]
    sender: dict[str, Any]


class ParsedCIFailure(BaseModel):
    """Normalized failure record extracted from a workflow_run webhook."""

    event_id: str = Field(description="Unique id for this failure event")
    received_at: datetime
    action: str
    workflow_run_id: int
    workflow_name: str
    run_number: int
    conclusion: str | None
    head_branch: str
    head_sha: str
    repo_full_name: str
    repo_clone_url: str
    workflow_url: str
    commit_message: str | None = None
    sender_login: str | None = None
    is_mock: bool = False
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class WebhookAck(BaseModel):
    status: str
    message: str
    failure: ParsedCIFailure | None = None
