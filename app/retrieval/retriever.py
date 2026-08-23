"""Query ChromaDB for code chunks relevant to a failure context."""

from __future__ import annotations

import logging

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.logging_config import log_stage
from app.retrieval.indexer import _get_chroma_client, _get_embedding_model, collection_name

logger = logging.getLogger(__name__)


def retrieve_context(
    *,
    repo_full_name: str,
    commit_sha: str,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    coll_name = collection_name(repo_full_name, commit_sha)
    client: chromadb.PersistentClient = _get_chroma_client()

    try:
        collection = client.get_collection(coll_name)
    except Exception as exc:
        raise LookupError(f"Collection '{coll_name}' not found. Index the repo first.") from exc

    model: SentenceTransformer = _get_embedding_model()
    query_embedding = model.encode([query], show_progress_bar=False).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    hits: list[dict] = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for doc, meta, distance in zip(documents, metadatas, distances):
        hits.append(
            {
                "document": doc,
                "metadata": meta,
                "distance": distance,
            }
        )

    log_stage(
        logger,
        "retrieval",
        "Context retrieved",
        repo=repo_full_name,
        sha=commit_sha,
        query_preview=query[:120],
        hit_count=len(hits),
    )
    return hits
