# SentinelPR

AI agent that watches GitHub CI, diagnoses test failures, generates a patch, verifies it in a sandbox, and opens a PR if tests pass.

Inspired by [YC RFS Fall 2026, idea #13: Self-Maintaining APIs](https://www.ycombinator.com/rfs).

## Current status: Step 1 — Webhook ingress

The FastAPI server receives GitHub `workflow_run` webhooks (or a mock payload) and logs normalized CI failure events to an in-memory store.

**Not yet built:** ChromaDB indexing, LangGraph pipeline, HF patch generation, Docker sandbox, PyGithub PR/issue creation, React dashboard.

## Quick start

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # optional; defaults work for local dev

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for interactive API docs.

## Test step 1 in isolation

### A. Mock endpoint (no GitHub needed)

```bash
curl -X POST http://127.0.0.1:8000/webhooks/github/mock
```

### B. Post the fixture as a real webhook shape

```bash
curl -X POST http://127.0.0.1:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: workflow_run" \
  -d @fixtures/mock_workflow_run_failure.json
```

### C. List recorded failures

```bash
curl http://127.0.0.1:8000/webhooks/failures
```

### D. Automated test script

```bash
# Parser only (no server)
python scripts/test_webhook.py --offline

# Full live test (server must be running)
python scripts/test_webhook.py
```

## Project layout

```
app/
  main.py              # FastAPI entrypoint
  config.py            # Settings from env
  models/webhook.py    # Pydantic models
  routers/webhook.py   # /webhooks/github, /webhooks/github/mock
  services/            # Parser + in-memory failure store
fixtures/
  mock_workflow_run_failure.json
scripts/
  test_webhook.py
```

## Environment variables

See `.env.example`. For step 1, only these matter:

| Variable | Purpose |
|---|---|
| `APP_ENV` | Set to `development` to enable `/webhooks/github/mock` |
| `LOG_LEVEL` | Logging verbosity |
| `GITHUB_WEBHOOK_SECRET` | Optional HMAC verification for real GitHub webhooks |

## Build order (from spec)

1. **Webhook ingress** ← you are here
2. ChromaDB repo indexing
3. LangGraph pipeline (stubbed nodes first)
4. Hugging Face patch generation
5. Docker sandbox test runner
6. PyGithub PR/issue creation
7. React dashboard

## License

MIT
