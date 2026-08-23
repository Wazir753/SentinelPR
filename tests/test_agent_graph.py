"""Phase 2 acceptance tests — LangGraph pipeline."""

from __future__ import annotations

from app.agent.graph import PipelineDeps, run_pipeline
from app.agent.models import is_valid_unified_diff
from app.agent.sandbox_stub import QueueSandboxRunner
from app.events import store as event_store
from app.webhooks.models import ParsedCIFailure
from app.webhooks.parser import load_mock_payload, parse_workflow_run_failure
from tests.conftest import TEST_REPO

VALID_DIFF = """--- a/test_repo/broken_math.py
+++ b/test_repo/broken_math.py
@@ -5,4 +5,4 @@
 def broken_add(a: float, b: float) -> float:
     \"\"\"Return the sum of two numbers.\"\"\"
-    return a - b  # bug: should add
+    return a + b  # fix
"""


def _sample_failure() -> ParsedCIFailure:
    payload = load_mock_payload()
    failure = parse_workflow_run_failure(payload, is_mock=True)
    assert failure is not None
    return failure


def test_stub_graph_full_trace(isolated_data_dirs):
    record = run_pipeline(
        _sample_failure(),
        local_repo_path=str(TEST_REPO),
    )

    assert record.status == "completed"
    assert record.outcome == "pr_opened"
    assert record.patch_attempts == 3
    assert record.pr_url is not None

    expected_order = [
        "triage_failure",
        "retrieve_context",
        "generate_patch",
        "sandbox_test",
        "generate_patch",
        "sandbox_test",
        "generate_patch",
        "sandbox_test",
        "open_pr",
    ]
    assert [step.split(":")[0] for step in record.trace] == expected_order


def test_graph_retry_path_with_queue_sandbox(isolated_data_dirs):
    sandbox = QueueSandboxRunner([False, False, True])
    deps = PipelineDeps(
        sandbox_runner=sandbox,
        patch_generator=lambda _state: VALID_DIFF,
    )

    record = run_pipeline(
        _sample_failure(),
        local_repo_path=str(TEST_REPO),
        deps=deps,
    )

    assert sandbox.calls == 3
    assert record.outcome == "pr_opened"
    assert record.patch_attempts == 3
    assert record.trace.count("sandbox_test:fail") == 2
    assert record.trace.count("sandbox_test:pass") == 1


def test_graph_files_issue_after_exhausted_retries(isolated_data_dirs):
    sandbox = QueueSandboxRunner([False, False, False])
    deps = PipelineDeps(
        sandbox_runner=sandbox,
        patch_generator=lambda _state: VALID_DIFF.replace("# fix", "# nofix"),
    )

    record = run_pipeline(
        _sample_failure(),
        local_repo_path=str(TEST_REPO),
        deps=deps,
    )

    assert record.outcome == "issue_filed"
    assert record.issue_url is not None
    assert record.patch_attempts == 3
    assert "file_issue" in record.trace[-1]


def test_pipeline_record_stored(isolated_data_dirs):
    failure = _sample_failure()
    run_pipeline(failure, local_repo_path=str(TEST_REPO))
    stored = event_store.get_pipeline(failure.event_id)
    assert stored is not None
    assert stored.status == "completed"
    assert is_valid_unified_diff(stored.patch_diff or "")
