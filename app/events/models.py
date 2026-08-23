"""Pipeline run tracking models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PipelineRecord(BaseModel):
    event_id: str
    repo: str
    status: str = "pending"
    trace: list[str] = Field(default_factory=list)
    patch_attempts: int = 0
    outcome: str | None = None
    pr_url: str | None = None
    issue_url: str | None = None
    diagnosis: str | None = None
    patch_diff: str | None = None
    error: str | None = None
