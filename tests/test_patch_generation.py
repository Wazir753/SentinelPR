"""Phase 2 acceptance tests — Hugging Face patch generation."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.agent.models import (
    extract_unified_diff,
    generate_patch_diff,
    is_valid_unified_diff,
    parse_hf_response,
)
from app.agent.nodes import make_generate_patch_node
from app.agent.state import AgentState

BROKEN_MATH_SOURCE = '''def broken_add(a: float, b: float) -> float:
    """Return the sum of two numbers."""
    return a - b  # bug: should add
'''

VALID_MODEL_OUTPUT = """Here is the fix:

```diff
--- a/test_repo/broken_math.py
+++ b/test_repo/broken_math.py
@@ -1,3 +1,3 @@
 def broken_add(a: float, b: float) -> float:
     \"\"\"Return the sum of two numbers.\"\"\"
-    return a - b  # bug: should add
+    return a + b
```
"""


def test_parse_hf_response_list():
    data = [{"generated_text": "--- a/foo\n+++ b/foo\n"}]
    assert parse_hf_response(data).startswith("--- a/foo")


def test_extract_unified_diff_from_fenced_block():
    diff = extract_unified_diff(VALID_MODEL_OUTPUT)
    assert is_valid_unified_diff(diff)
    assert "-    return a - b" in diff
    assert "+    return a + b" in diff


def test_generate_patch_node_stub_produces_valid_diff():
    node = make_generate_patch_node(use_hf=False)
    result = node(
        AgentState(
            event_id="test",
            traceback="assert -1 == 3",
            context_text=BROKEN_MATH_SOURCE,
            patch_attempt=0,
            trace=[],
        )
    )
    assert is_valid_unified_diff(result["patch_diff"])


@patch("app.agent.models.httpx.Client")
def test_generate_patch_diff_calls_hf_api(mock_client_cls):
    mock_response = httpx.Response(
        200,
        json=[{"generated_text": VALID_MODEL_OUTPUT}],
        request=httpx.Request("POST", "https://example.com"),
    )
    mock_client = mock_client_cls.return_value.__enter__.return_value
    mock_client.post.return_value = mock_response

    diff = generate_patch_diff(
        traceback="FAILED test_broken_add",
        context=BROKEN_MATH_SOURCE,
        token="test-token",
    )

    assert is_valid_unified_diff(diff)
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer test-token"


def test_generate_patch_diff_requires_token():
    with patch("app.agent.models.settings.hf_api_token", ""):
        with pytest.raises(RuntimeError, match="HF_API_TOKEN"):
            generate_patch_diff("trace", "context", token="")


@pytest.mark.integration
def test_generate_patch_diff_live_hf():
    """Optional live test — skipped unless HF_API_TOKEN is set."""
    from app.config import settings

    if not settings.hf_api_token:
        pytest.skip("HF_API_TOKEN not configured")

    diff = generate_patch_diff(
        traceback="FAILED test_broken_add - assert -1 == 3",
        context=BROKEN_MATH_SOURCE,
    )
    assert is_valid_unified_diff(diff)
