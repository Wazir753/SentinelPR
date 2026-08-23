"""LangGraph orchestrator for the SentinelPR fix loop."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from langgraph.graph import END, StateGraph

from app.agent.nodes import (
    file_issue_node,
    make_generate_patch_node,
    make_sandbox_test_node,
    make_triage_failure_node,
    open_pr_node,
    retrieve_context_node,
)
from app.agent.sandbox_stub import SandboxRunner, default_stub_sandbox
from app.agent.state import AgentState
from app.events import store as event_store
from app.events.models import PipelineRecord
from app.logging_config import log_stage
from app.webhooks.models import ParsedCIFailure

logger = logging.getLogger(__name__)

FIXTURE_TRACEBACK = Path(__file__).resolve().parents[2] / "fixtures" / "mock_traceback.txt"
MAX_RETRIES = 2


@dataclass
class PipelineDeps:
    sandbox_runner: SandboxRunner = field(default_factory=lambda: default_stub_sandbox)
    use_hf_patch: bool = False
    patch_generator: Callable[[AgentState], str] | None = None
    traceback_fixture: Path | None = None


def _after_sandbox(state: AgentState) -> str:
    if state.get("sandbox_passed"):
        return "open_pr"
    attempt = state.get("patch_attempt", 0)
    if attempt <= MAX_RETRIES:
        return "generate_patch"
    return "file_issue"


def build_graph(deps: PipelineDeps | None = None) -> StateGraph:
    deps = deps or PipelineDeps()
    graph = StateGraph(AgentState)

    graph.add_node("triage_failure", make_triage_failure_node(deps.traceback_fixture or FIXTURE_TRACEBACK))
    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node(
        "generate_patch",
        make_generate_patch_node(use_hf=deps.use_hf_patch, patch_generator=deps.patch_generator),
    )
    graph.add_node("sandbox_test", make_sandbox_test_node(deps.sandbox_runner))
    graph.add_node("open_pr", open_pr_node)
    graph.add_node("file_issue", file_issue_node)

    graph.set_entry_point("triage_failure")
    graph.add_edge("triage_failure", "retrieve_context")
    graph.add_edge("retrieve_context", "generate_patch")
    graph.add_edge("generate_patch", "sandbox_test")
    graph.add_conditional_edges(
        "sandbox_test",
        _after_sandbox,
        {
            "open_pr": "open_pr",
            "generate_patch": "generate_patch",
            "file_issue": "file_issue",
        },
    )
    graph.add_edge("open_pr", END)
    graph.add_edge("file_issue", END)

    return graph


def failure_to_initial_state(
    failure: ParsedCIFailure,
    *,
    local_repo_path: str | None = None,
) -> AgentState:
    return AgentState(
        event_id=failure.event_id,
        repo_full_name=failure.repo_full_name,
        head_sha=failure.head_sha,
        repo_clone_url=failure.repo_clone_url,
        workflow_run_id=failure.workflow_run_id,
        workflow_url=failure.workflow_url,
        is_mock=failure.is_mock,
        local_repo_path=local_repo_path,
        max_retries=MAX_RETRIES,
        patch_attempt=0,
        trace=[],
    )


def run_pipeline(
    failure: ParsedCIFailure,
    *,
    local_repo_path: str | None = None,
    deps: PipelineDeps | None = None,
) -> PipelineRecord:
    event_id = failure.event_id
    record = PipelineRecord(event_id=event_id, status="running", repo=failure.repo_full_name)
    event_store.record_pipeline(record)

    log_stage(logger, "pipeline", "Pipeline started", event_id=event_id)

    try:
        graph = build_graph(deps).compile()
        initial = failure_to_initial_state(failure, local_repo_path=local_repo_path)
        final_state = graph.invoke(initial)

        record.status = "completed"
        record.trace = final_state.get("trace", [])
        record.patch_attempts = final_state.get("patch_attempt", 0)
        record.outcome = final_state.get("outcome")
        record.pr_url = final_state.get("pr_url")
        record.issue_url = final_state.get("issue_url")
        record.diagnosis = final_state.get("diagnosis")
        record.patch_diff = final_state.get("patch_diff")

        log_stage(
            logger,
            "pipeline",
            "Pipeline completed",
            event_id=event_id,
            outcome=record.outcome,
            patch_attempts=record.patch_attempts,
        )
    except Exception as exc:
        record.status = "failed"
        record.error = str(exc)
        log_stage(logger, "pipeline", "Pipeline failed", event_id=event_id, error=str(exc))
        raise
    finally:
        event_store.update_pipeline(record)

    return record
