#!/usr/bin/env python3
"""
Isolation test for step 1 — webhook ingress.

Usage (server must be running):
    python scripts/test_webhook.py

Or test the parser without a server:
    python scripts/test_webhook.py --offline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000"
FIXTURE = ROOT / "fixtures" / "mock_workflow_run_failure.json"


def test_offline_parser() -> None:
    sys.path.insert(0, str(ROOT))
    from app.services.webhook_parser import load_mock_payload, parse_workflow_run_failure

    payload = load_mock_payload()
    failure = parse_workflow_run_failure(payload, is_mock=True)
    assert failure is not None, "Expected failure to be parsed"
    assert failure.conclusion == "failure"
    assert failure.repo_full_name == "Wazir753/SentinelPR"
    print("offline parser OK:", failure.event_id, failure.workflow_name)


def test_live_mock_endpoint(base_url: str) -> None:
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        health = client.get("/health")
        health.raise_for_status()
        print("health:", health.json())

        resp = client.post("/webhooks/github/mock")
        resp.raise_for_status()
        data = resp.json()
        print("mock webhook:", json.dumps(data, indent=2, default=str))
        assert data["status"] == "accepted"
        assert data["failure"]["is_mock"] is True

        failures = client.get("/webhooks/failures")
        failures.raise_for_status()
        items = failures.json()
        print(f"stored failures: {len(items)}")
        assert len(items) >= 1


def test_live_fixture_post(base_url: str) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "workflow_run",
    }
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        resp = client.post("/webhooks/github", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        print("fixture POST:", json.dumps(data, indent=2, default=str))
        assert data["status"] == "accepted"


def main() -> None:
    parser = argparse.ArgumentParser(description="Test SentinelPR webhook (step 1)")
    parser.add_argument("--offline", action="store_true", help="Test parser only, no server")
    parser.add_argument("--base-url", default=BASE_URL, help="API base URL")
    args = parser.parse_args()

    if args.offline:
        test_offline_parser()
        return

    base_url = args.base_url.rstrip("/")
    test_live_mock_endpoint(base_url)
    test_live_fixture_post(base_url)
    print("\nAll step-1 webhook tests passed.")


if __name__ == "__main__":
    main()
