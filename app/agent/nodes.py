"""LangGraph pipeline node implementations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from app.agent.models import generate_patch_diff, is_valid_unified_diff
from app.agent.sandbox_stub import SandboxRunner, default_stub_sandbox
from app.agent.state import AgentState
from app.logging_config import log_stage
from app.retrieval.indexer import collection_name, index_from_local
from app.retrieval.retriever import retrieve_context

logger = logging.getLogger(__name__)

STUB_PATCH_TEMPLATE = """--- a/{file_path}
+++ b/{file_path}
@@ -1,1 +1,1 @@
-{old_line}
+{new_line}
"""


def _append_trace(state: AgentState, node: str, detail: str = "") -> list[str]:
    entry = f"{node}" if not detail else f"{node}:{detail}"
    return [entry]


def make_triage_failure_node(default_traceback_path: Path | None = None):
    def triage_failure(state: AgentState) -> dict:
        event_id = state["event_id"]
        if state.get("traceback"):
            traceback = state["traceback"]
        elif default_traceback_path and default_traceback_path.exists():
            traceback = default_traceback_path.read_text(encoding="utf-8")
        else:
            traceback = (
                "FAILED test_repo/test_broken_math.py::test_broken_add - AssertionError\n"
                "E       assert -1 == 3\n"
                "E        +  where -1 = broken_add(2, 1)\n"
                "test_repo/broken_math.py:8: AssertionError"
            )

        diagnosis = (
            f"Test failure in {state.get('repo_full_name', 'unknown')}: "
            f"{traceback.strip().splitlines()[0]}"
        )
        failing_test = "test_broken_add"
        for line in traceback.splitlines():
            if "FAILED" in line and "::" in line:
                failing_test = line.split("::")[-1].split()[0]
                break

        log_stage(
            logger,
            "triage_failure",
            "Failure triaged",
            event_id=event_id,
            failing_test=failing_test,
        )
        return {
            "traceback": traceback,
            "diagnosis": diagnosis,
            "failing_test": failing_test,
            "trace": _append_trace(state, "triage_failure", failing_test),
        }

    return triage_failure


def retrieve_context_node(state: AgentState) -> dict:
    event_id = state["event_id"]
    repo = state["repo_full_name"]
    sha = state["head_sha"]
    query = f"{state.get('failing_test', '')} {state.get('traceback', '')[:500]}"

    local_path = state.get("local_repo_path")
    coll = collection_name(repo, sha)
    try:
        from app.retrieval.indexer import _get_chroma_client

        _get_chroma_client().get_collection(coll)
    except Exception:
        if local_path:
            log_stage(logger, "retrieve_context", "Indexing local repo before retrieval", event_id=event_id)
            index_from_local(Path(local_path), repo_full_name=repo, commit_sha=sha)
        else:
            log_stage(
                logger,
                "retrieve_context",
                "No index found and no local_repo_path provided",
                event_id=event_id,
                collection=coll,
            )

    try:
        hits = retrieve_context(repo_full_name=repo, commit_sha=sha, query=query, top_k=5)
    except LookupError:
        hits = []

    context_text = "\n\n---\n\n".join(hit["document"] for hit in hits)
    log_stage(
        logger,
        "retrieve_context",
        "Context retrieved",
        event_id=event_id,
        hit_count=len(hits),
    )
    return {
        "context_chunks": hits,
        "context_text": context_text,
        "trace": _append_trace(state, "retrieve_context", f"{len(hits)}_hits"),
    }


def make_generate_patch_node(
    *,
    use_hf: bool = False,
    patch_generator: Callable[[AgentState], str] | None = None,
):
    def generate_patch(state: AgentState) -> dict:
        attempt = state.get("patch_attempt", 0) + 1
        event_id = state["event_id"]

        if patch_generator is not None:
            diff = patch_generator(state)
        elif use_hf:
            diff = generate_patch_diff(
                state.get("traceback", ""),
                state.get("context_text", ""),
            )
        else:
            diff = STUB_PATCH_TEMPLATE.format(
                file_path="test_repo/broken_math.py",
                old_line="    return a - b  # bug: should add",
                new_line="    return a + b  # fix",
            )
            if attempt < 3:
                diff = diff.replace("# fix", f"# attempt_{attempt}")

        if not is_valid_unified_diff(diff):
            raise ValueError("Generated patch is not a valid unified diff")

        log_stage(
            logger,
            "generate_patch",
            "Patch generated",
            event_id=event_id,
            patch_attempt=attempt,
            use_hf=use_hf,
        )
        return {
            "patch_diff": diff,
            "patch_attempt": attempt,
            "trace": _append_trace(state, "generate_patch", f"attempt_{attempt}"),
        }

    return generate_patch


def make_sandbox_test_node(sandbox_runner: SandboxRunner | None = None):
    runner = sandbox_runner or default_stub_sandbox

    def sandbox_test(state: AgentState) -> dict:
        event_id = state["event_id"]
        passed, output = runner(state)
        log_stage(
            logger,
            "sandbox_test",
            "Sandbox test completed",
            event_id=event_id,
            passed=passed,
            patch_attempt=state.get("patch_attempt", 0),
        )
        return {
            "sandbox_passed": passed,
            "sandbox_output": output,
            "trace": _append_trace(state, "sandbox_test", "pass" if passed else "fail"),
        }

    return sandbox_test


def open_pr_node(state: AgentState) -> dict:
    event_id = state["event_id"]
    pr_url = (
        f"https://github.com/{state['repo_full_name']}/pull/999"
        f"?sentinelpr_event={event_id}"
    )
    explanation = (
        f"## SentinelPR automated fix (AI-generated — requires human review)\n\n"
        f"**Diagnosis:** {state.get('diagnosis', 'Unknown')}\n\n"
        f"**Patch attempts:** {state.get('patch_attempt', 0)}\n\n"
        f"This PR was opened automatically by SentinelPR. Please review before merging."
    )
    log_stage(logger, "open_pr", "PR opened (stub)", event_id=event_id, pr_url=pr_url)
    return {
        "outcome": "pr_opened",
        "pr_url": pr_url,
        "trace": _append_trace(state, "open_pr", "stub"),
    }


def file_issue_node(state: AgentState) -> dict:
    event_id = state["event_id"]
    issue_url = (
        f"https://github.com/{state['repo_full_name']}/issues/999"
        f"?sentinelpr_event={event_id}"
    )
    log_stage(logger, "file_issue", "Issue filed (stub)", event_id=event_id, issue_url=issue_url)
    return {
        "outcome": "issue_filed",
        "issue_url": issue_url,
        "trace": _append_trace(state, "file_issue", "stub"),
    }
