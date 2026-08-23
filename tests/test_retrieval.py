"""Phase 1 acceptance tests — repo indexing and retrieval."""

from __future__ import annotations

import pytest

from app.retrieval.chunker import chunk_repository
from app.retrieval.indexer import collection_name, index_from_local
from app.retrieval.retriever import retrieve_context
from tests.conftest import TEST_REPO


def test_chunk_repository_finds_functions():
    chunks = chunk_repository(TEST_REPO)
    names = {chunk.name for chunk in chunks}
    assert "add" in names
    assert "divide" in names
    assert "subtract" in names


def test_index_from_local_creates_nonempty_collection(isolated_data_dirs):
    summary = index_from_local(
        TEST_REPO,
        repo_full_name="sentinelpr/test-repo",
        commit_sha="deadbeef00000000000000000000000000000000",
    )
    assert summary["chunk_count"] >= 4
    assert summary["collection"] == collection_name(
        "sentinelpr/test-repo",
        "deadbeef00000000000000000000000000000000",
    )


def test_retriever_returns_known_function_in_top_results(isolated_data_dirs):
    repo = "sentinelpr/test-repo"
    sha = "deadbeef00000000000000000000000000000000"
    index_from_local(TEST_REPO, repo_full_name=repo, commit_sha=sha)

    hits = retrieve_context(
        repo_full_name=repo,
        commit_sha=sha,
        query="function that divides two numbers and returns the quotient",
        top_k=3,
    )
    assert hits, "Expected at least one retrieval hit"
    top_names = [hit["metadata"]["name"] for hit in hits]
    assert "divide" in top_names
