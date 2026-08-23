"""Injectable sandbox runner (stub for Phase 2, Docker in Phase 3)."""

from __future__ import annotations

from collections import deque
from typing import Callable, Protocol

from app.agent.state import AgentState


class SandboxRunner(Protocol):
    def __call__(self, state: AgentState) -> tuple[bool, str]: ...


def default_stub_sandbox(state: AgentState) -> tuple[bool, str]:
    """Phase 2 stub: passes when patch contains 'fix' or attempt exceeds retries."""
    attempt = state.get("patch_attempt", 1)
    diff = state.get("patch_diff", "")
    if "fix" in diff.lower() or attempt >= 3:
        return True, f"stub pytest passed on attempt {attempt}"
    return False, f"stub pytest failed on attempt {attempt}"


class QueueSandboxRunner:
    """Returns queued pass/fail results — used to exercise retry paths in tests."""

    def __init__(self, results: list[bool]):
        self._results: deque[bool] = deque(results)
        self.calls = 0

    def __call__(self, state: AgentState) -> tuple[bool, str]:
        self.calls += 1
        if self._results:
            passed = self._results.popleft()
        else:
            passed = False
        status = "passed" if passed else "failed"
        return passed, f"queued sandbox {status} on attempt {self.calls}"


def always_pass(_: AgentState) -> tuple[bool, str]:
    return True, "sandbox passed"


def always_fail(state: AgentState) -> tuple[bool, str]:
    attempt = state.get("patch_attempt", 0)
    return False, f"sandbox failed on attempt {attempt}"
