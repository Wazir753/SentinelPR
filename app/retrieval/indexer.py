"""Clone repositories and index Python code into ChromaDB."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

import chromadb
from git import Repo
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.logging_config import log_stage
from app.retrieval.chunker import CodeChunk, chunk_repository

logger = logging.getLogger(__name__)

_embedding_model: SentenceTransformer | None = None


def collection_name(repo_full_name: str, commit_sha: str) -> str:
    """Build a Chroma-safe collection id from repo + commit."""
    safe_repo = repo_full_name.replace("/", "__")
    return f"{safe_repo}__{commit_sha[:12]}"


def reset_embedding_cache() -> None:
    """Clear cached embedding model (used in tests)."""
    global _embedding_model
    _embedding_model = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        log_stage(logger, "retrieval", "Loading embedding model", model=settings.embedding_model)
        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def _get_chroma_client() -> chromadb.PersistentClient:
    settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(settings.chroma_persist_dir))


def clone_repository(clone_url: str, commit_sha: str, repo_full_name: str) -> Path:
    """Clone a repo and checkout the target commit SHA."""
    settings.repo_clone_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.repo_clone_dir / repo_full_name.replace("/", "__") / commit_sha[:12]

    if dest.exists():
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    log_stage(
        logger,
        "retrieval",
        "Cloning repository",
        repo=repo_full_name,
        sha=commit_sha,
        dest=str(dest),
    )
    repo = Repo.clone_from(clone_url, dest, depth=1)
    repo.git.checkout(commit_sha)
    return dest


def prepare_local_repository(local_path: Path) -> Path:
    """Use a local directory as the repo root (for tests and offline indexing)."""
    resolved = local_path.resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"Local repository path not found: {resolved}")
    return resolved


def index_repository(
    *,
    repo_full_name: str,
    commit_sha: str,
    repo_root: Path,
) -> dict:
    """
    Chunk, embed, and upsert all Python functions/classes into ChromaDB.

    Returns summary metadata including collection name and chunk count.
    """
    chunks = chunk_repository(repo_root)
    if not chunks:
        raise ValueError(f"No indexable Python chunks found under {repo_root}")

    coll_name = collection_name(repo_full_name, commit_sha)
    client = _get_chroma_client()
    model = _get_embedding_model()

    try:
        client.delete_collection(coll_name)
    except Exception:
        pass

    collection = client.create_collection(name=coll_name, metadata={"hnsw:space": "cosine"})
    documents = [_chunk_document(chunk) for chunk in chunks]
    embeddings = model.encode(documents, show_progress_bar=False).tolist()
    ids = [f"{chunk.file_path}:{chunk.chunk_type}:{chunk.name}:{chunk.start_line}" for chunk in chunks]
    metadatas = [
        {
            "repo": repo_full_name,
            "sha": commit_sha,
            "file_path": chunk.file_path,
            "chunk_type": chunk.chunk_type,
            "name": chunk.name,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
        }
        for chunk in chunks
    ]

    collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    summary = {
        "collection": coll_name,
        "repo": repo_full_name,
        "sha": commit_sha,
        "chunk_count": len(chunks),
        "persist_dir": str(settings.chroma_persist_dir),
    }
    log_stage(logger, "retrieval", "Repository indexed", **summary)
    return summary


def index_from_clone(clone_url: str, commit_sha: str, repo_full_name: str) -> dict:
    repo_root = clone_repository(clone_url, commit_sha, repo_full_name)
    return index_repository(
        repo_full_name=repo_full_name,
        commit_sha=commit_sha,
        repo_root=repo_root,
    )


def index_from_local(local_path: Path, repo_full_name: str, commit_sha: str) -> dict:
    repo_root = prepare_local_repository(local_path)
    return index_repository(
        repo_full_name=repo_full_name,
        commit_sha=commit_sha,
        repo_root=repo_root,
    )


def _chunk_document(chunk: CodeChunk) -> str:
    return (
        f"File: {chunk.file_path}\n"
        f"Kind: {chunk.chunk_type}\n"
        f"Name: {chunk.name}\n"
        f"Lines: {chunk.start_line}-{chunk.end_line}\n\n"
        f"{chunk.source}"
    )


def git_head_sha(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()
