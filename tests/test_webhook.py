"""Phase 1 acceptance tests — webhook ingress."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.events import store as event_store
from app.main import app
from tests.conftest import FIXTURE_PAYLOAD

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["phase"] == 1


def test_webhook_fixture_payload():
    payload = json.loads(FIXTURE_PAYLOAD.read_text(encoding="utf-8"))
    response = client.post(
        "/webhooks/github",
        json=payload,
        headers={"X-GitHub-Event": "workflow_run"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["failure"]["repo_full_name"] == "Wazir753/SentinelPR"
    assert body["failure"]["conclusion"] == "failure"
    assert body["failure"]["workflow_run_id"] == 9876543210
    assert body["failure"]["head_sha"].startswith("abc123")


def test_webhook_mock_endpoint():
    response = client.post("/webhooks/github/mock")
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["failure"]["is_mock"] is True


def test_webhook_ignores_success_conclusion():
    payload = json.loads(FIXTURE_PAYLOAD.read_text(encoding="utf-8"))
    payload["workflow_run"]["conclusion"] = "success"
    response = client.post(
        "/webhooks/github",
        json=payload,
        headers={"X-GitHub-Event": "workflow_run"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert event_store.list_failures() == []


def test_list_failures_endpoint():
    client.post("/webhooks/github/mock")
    response = client.get("/webhooks/failures")
    assert response.status_code == 200
    failures = response.json()
    assert len(failures) == 1
    assert failures[0]["event_id"].startswith("wf-")


def test_status_endpoint_lists_events():
    client.post("/webhooks/github/mock")
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == 1
    assert len(body["events"]) == 1
    assert body["events"][0]["repo"] == "Wazir753/SentinelPR"
