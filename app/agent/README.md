# Phase 2 — LangGraph agent pipeline

Graph flow:

```
triage_failure → retrieve_context → generate_patch → sandbox_test
                                                      ↓ pass → open_pr
                                                      ↓ fail (retries left) → generate_patch
                                                      ↓ fail (exhausted) → file_issue
```

- `generate_patch` uses Hugging Face `Qwen/Qwen2.5-Coder-7B-Instruct` when `HF_API_TOKEN` is set.
- `sandbox_test` and GitHub nodes are stubs until Phase 3.
