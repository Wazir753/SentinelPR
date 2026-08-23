# SentinelPR

**Autonomous code-repair agent for Python CI failures.**

SentinelPR watches a GitHub repository's CI pipeline. When a test run fails, it diagnoses the failure, retrieves relevant code via RAG, generates a candidate patch, verifies it in an isolated Docker sandbox, and opens a pull request for human review — or files a diagnostic issue if it cannot fix the problem.

Inspired by [YC RFS Fall 2026 — Self-Maintaining APIs](https://www.ycombinator.com/rfs).

[![CI](https://github.com/Wazir753/SentinelPR/actions/workflows/ci.yml/badge.svg)](https://github.com/Wazir753/SentinelPR/actions/workflows/ci.yml)

---

## Architecture

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

Full design notes: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Build status

| Phase | Scope | Status |
|-------|-------|--------|
| **1** | Webhook ingress + ChromaDB repo indexing | ✅ **Complete** |
| **2** | LangGraph pipeline + HF patch generation | 🔜 Next |
| **3** | Docker sandbox + PyGithub PR/issue | Planned |
| **4** | React dashboard | Planned |

---

## Quick start

**Requirements:** Python 3.11+, pip

```bash
git clone https://github.com/Wazir753/SentinelPR.git
cd SentinelPR
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # optional for local dev

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Phase 1 — Verify it yourself

### 1. Run the automated acceptance suite

```bash
pytest tests/ -v
```

First run downloads the embedding model (~90 MB) and may take a minute.

### 2. Test webhook ingress (no GitHub needed)

```bash
# With server running:
curl -X POST http://127.0.0.1:8000/webhooks/github/mock

# Or post the fixture directly:
curl -X POST http://127.0.0.1:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: workflow_run" \
  -d @fixtures/mock_workflow_run_failure.json
```

Structured JSON logs appear on stdout with `"stage": "webhook_ingress"`.

### 3. Index the bundled test repo

```bash
python scripts/index_repo.py test_repo --repo sentinelpr/test-repo
```

### 4. Query indexed code (Python REPL)

```python
from app.retrieval.retriever import retrieve_context

hits = retrieve_context(
    repo_full_name="sentinelpr/test-repo",
    commit_sha="<sha printed by index_repo.py>",
    query="function that divides two numbers",
    top_k=3,
)
print([h["metadata"]["name"] for h in hits])  # expect 'divide' in results
```

---

## Project structure

```
app/
├── main.py                 # FastAPI entrypoint
├── config.py               # Environment configuration
├── logging_config.py       # JSON structured logging
├── webhooks/               # GitHub workflow_run ingress
├── retrieval/              # AST chunking, ChromaDB indexing & retrieval
├── events/                 # Failure event store
├── api/                    # /api/status (expanded in Phase 4)
├── agent/                  # LangGraph pipeline (Phase 2)
├── sandbox/                # Docker test runner (Phase 3)
└── github_client/          # PyGithub App client (Phase 3)
tests/                      # pytest acceptance tests
test_repo/                  # Fixture Python repo for indexing
fixtures/                   # Mock webhook payloads
frontend/                   # React dashboard (Phase 4)
docs/ARCHITECTURE.md        # Detailed architecture reference
```

---

## Configuration

Copy `.env.example` to `.env`. Phase 1 only requires defaults; later phases need:

| Variable | Phase | Purpose |
|----------|-------|---------|
| `APP_ENV` | 1 | `development` enables mock webhook endpoint |
| `GITHUB_WEBHOOK_SECRET` | 1 | HMAC verification for real webhooks |
| `CHROMA_PERSIST_DIR` | 1 | ChromaDB storage path (default: `./data/chroma`) |
| `HF_API_TOKEN` | 2 | Hugging Face Inference API for patch generation |
| `GITHUB_APP_ID` | 3 | GitHub App authentication |
| `GITHUB_APP_PRIVATE_KEY_PATH` | 3 | Path to GitHub App PEM key |
| `NOTIFY_WEBHOOK_URL` | 3+ | Outbound notification webhook |

---

## Design principles

- **Human approval only** — SentinelPR proposes PRs; it never auto-merges.
- **Sandbox gate** — every patch must pass `pytest` in an isolated container before a PR is opened.
- **Bounded cost** — max 2 patch retries per failure event.
- **Structured traceability** — every pipeline stage emits JSON logs with `stage` and `event_id`.

---

## License

MIT — see [LICENSE](LICENSE).
