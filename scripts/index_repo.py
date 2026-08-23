#!/usr/bin/env python3
"""CLI helper to index a local repository into ChromaDB (Phase 1 verification)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval.indexer import git_head_sha, index_from_local  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Index a local Python repo into ChromaDB")
    parser.add_argument("path", type=Path, help="Path to repository root")
    parser.add_argument("--repo", required=True, help="Logical repo name, e.g. owner/repo")
    parser.add_argument("--sha", help="Commit SHA (defaults to git HEAD when available)")
    args = parser.parse_args()

    sha = args.sha
    if not sha:
        try:
            sha = git_head_sha(args.path)
        except Exception as exc:
            raise SystemExit(f"Could not resolve git HEAD; pass --sha explicitly. ({exc})") from exc

    summary = index_from_local(args.path, repo_full_name=args.repo, commit_sha=sha)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
