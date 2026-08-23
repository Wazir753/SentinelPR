# Architecture

SentinelPR is an autonomous code-repair agent for Python repositories using GitHub Actions and pytest.

## System diagram

```mermaid
flowchart TB
    subgraph GitHub
        REPO[Customer Repository]
        CI[GitHub Actions CI]
        PR[Pull Request]
        ISSUE[Diagnostic Issue]
    end

    subgraph SentinelPR
        WH[FastAPI Webhook Ingress]
        LG[LangGraph Orchestrator]
        TRIAGE[triage_failure]
        RAG[retrieve_context]
        GEN[generate_patch]
        SB[sandbox_test]
        OPEN[open_pr]
        FILE[file_issue]
        CHROMA[(ChromaDB)]
        HF[Hugging Face Inference API]
        DOCKER[Docker Sandbox]
        GH[PyGithub App Client]
        STATUS[/status API]
        DASH[React Dashboard]
        NOTIFY[Notification Webhook]
    end

    REPO --> CI
    CI -->|workflow_run failure| WH
    WH --> LG
    LG --> TRIAGE --> RAG --> GEN --> SB
    RAG --> CHROMA
    GEN --> HF
    SB --> DOCKER
    SB -->|pass| OPEN
    SB -->|fail ≤2 retries| GEN
    SB -->|fail after retries| FILE
    OPEN --> GH --> PR
    FILE --> GH --> ISSUE
    OPEN --> NOTIFY
    FILE --> NOTIFY
    WH --> STATUS --> DASH
```

## Phase map

| Phase | Components | Status |
|-------|------------|--------|
| **1** | Webhook ingress, AST chunking, ChromaDB indexing, structured JSON logging | ✅ Complete |
| **2** | LangGraph pipeline, HF patch generation | Planned |
| **3** | Docker sandbox, PyGithub PR/issue creation | Planned |
| **4** | `/status` dashboard (React 16) | Planned |

## Data flow (failure → fix)

1. GitHub Actions reports `workflow_run` with `conclusion: failure`.
2. Webhook ingress validates the payload and records a structured failure event.
3. The repo is cloned at the failing SHA and indexed into ChromaDB (function/class chunks, MiniLM embeddings).
4. LangGraph triages the failure and retrieves relevant code context.
5. Qwen2.5-Coder-7B-Instruct generates a unified diff from traceback + context.
6. A Docker container (`--network none`, 60s timeout) applies the diff and runs `pytest`.
7. On pass → GitHub App opens a PR (human approval required). On repeated fail → diagnostic issue.

## Security constraints

- LLM-generated code never runs outside an isolated Docker container.
- Containers have no network egress and are always destroyed after each attempt.
- Credentials load from environment variables only; nothing secret is committed.
- No auto-merge — every fix is a proposed PR.

## Repository layout

```
app/
  main.py                 FastAPI entrypoint
  config.py               Environment configuration
  logging_config.py       JSON structured logging
  webhooks/               GitHub workflow_run ingress
  retrieval/              Chunking, indexing, ChromaDB queries
  events/                 In-memory failure event store
  api/                    /status endpoint (Phase 4 expansion)
  agent/                  LangGraph pipeline (Phase 2)
  sandbox/                Docker test runner (Phase 3)
  github_client/          PyGithub App client (Phase 3)
frontend/                 React 16 dashboard (Phase 4)
tests/                    pytest acceptance suite
test_repo/                Fixture repo for indexing tests
fixtures/                 Mock webhook payloads
```
