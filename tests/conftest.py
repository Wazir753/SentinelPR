"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from app.events import store as event_store
from app.retrieval.indexer import reset_embedding_cache

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_REPO = PROJECT_ROOT / "test_repo"
FIXTURE_PAYLOAD = PROJECT_ROOT / "fixtures" / "mock_workflow_run_failure.json"


@pytest.fixture(autouse=True)
def clear_event_store():
    event_store.clear_failures()
    yield
    event_store.clear_failures()


@pytest.fixture
def isolated_data_dirs(tmp_path, monkeypatch):
    chroma_dir = tmp_path / "chroma"
    clone_dir = tmp_path / "repos"
    monkeypatch.setattr(settings, "chroma_persist_dir", chroma_dir)
    monkeypatch.setattr(settings, "repo_clone_dir", clone_dir)
    reset_embedding_cache()
    yield {"chroma": chroma_dir, "repos": clone_dir}
    reset_embedding_cache()
