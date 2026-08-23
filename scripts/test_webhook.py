#!/usr/bin/env python3
"""Manual webhook smoke test (pytest covers acceptance criteria)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "mock_workflow_run_failure.json"
DEFAULT_URL = "http://127.0.0.1:8000"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_URL)
    parser.add_argument("--mock", action="store_true", help="Hit /webhooks/github/mock")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    with httpx.Client(base_url=base, timeout=15.0) as client:
        if args.mock:
            resp = client.post("/webhooks/github/mock")
        else:
            payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
            resp = client.post(
                "/webhooks/github",
                json=payload,
                headers={"X-GitHub-Event": "workflow_run"},
            )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2, default=str))


if __name__ == "__main__":
    main()
