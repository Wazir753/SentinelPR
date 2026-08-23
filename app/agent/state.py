"""LangGraph agent state schema."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict, total=False):
    event_id: str
    repo_full_name: str
    head_sha: str
    repo_clone_url: str
    workflow_run_id: int
    workflow_url: str
    is_mock: bool
    local_repo_path: str | None

    diagnosis: str
    traceback: str
    failing_test: str

    context_chunks: list[dict[str, Any]]
    context_text: str

    patch_diff: str
    patch_attempt: int
    max_retries: int

    sandbox_passed: bool
    sandbox_output: str

    outcome: str | None
    pr_url: str | None
    issue_url: str | None

    trace: Annotated[list[str], operator.add]
    error: str | None
