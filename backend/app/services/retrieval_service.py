# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Retrieval pipeline: embed the query, hybrid-search Weaviate for a candidate
# set scoped to what current_user can read (own docs + their departments'
# active docs), then rerank that candidate set with a cross-encoder and
# return the top_k. Kept framework-agnostic so it's reusable from the chat
# engine (Phase 5) as well as the debug endpoint below.
#
# retrieve_context is the chat-facing variant — same pipeline, wrapped in
# per-stage timing logs. It used to also fold the user's own long-term
# memory summaries into the candidate pool (Phase 6); that's been removed
# (this app is RAG-over-documents, not chat-history recall, and it was
# adding a DB round-trip — occasionally a multi-second one — to every
# message for a capability nobody used). ContextItem.source and "memory" are
# left in the type so the door isn't fully closed, but nothing produces a
# memory-sourced item anymore.

import logging
import time
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from app.models.user import User
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.reranker.base import Reranker
from app.vectorstore.base import VectorRepository

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
DEFAULT_CANDIDATE_LIMIT = 20
DEFAULT_ALPHA = 0.5

ContextSource = Literal["document", "memory"]


@dataclass(frozen=True)
class RankedChunk:
    document_id: int
    document_version_id: int
    chunk_index: int
    content: str
    hybrid_score: float
    rerank_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


def retrieve_chunks(
    *,
    current_user: User,
    query: str,
    embedding_provider: EmbeddingProvider,
    vector_repository: VectorRepository,
    reranker: Reranker,
    top_k: int = DEFAULT_TOP_K,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    alpha: float = DEFAULT_ALPHA,
) -> list[RankedChunk]:
    department_ids = [department.id for department in current_user.departments]

    stage_start = time.monotonic()
    query_vector = embedding_provider.embed_query(query)
    logger.debug("retrieve_chunks: embed_query took %.3fs", time.monotonic() - stage_start)

    stage_start = time.monotonic()
    candidates = vector_repository.hybrid_search(
        query=query,
        query_vector=query_vector,
        owner_id=current_user.id,
        department_ids=department_ids,
        limit=candidate_limit,
        alpha=alpha,
    )
    logger.debug(
        "retrieve_chunks: hybrid_search took %.3fs (%d candidates)",
        time.monotonic() - stage_start,
        len(candidates),
    )
    if not candidates:
        return []

    stage_start = time.monotonic()
    ranked_indices = reranker.rerank(query, [candidate.content for candidate in candidates])
    logger.debug("retrieve_chunks: rerank took %.3fs", time.monotonic() - stage_start)

    return [
        RankedChunk(
            document_id=candidates[ranked.index].document_id,
            document_version_id=candidates[ranked.index].document_version_id,
            chunk_index=candidates[ranked.index].chunk_index,
            content=candidates[ranked.index].content,
            hybrid_score=candidates[ranked.index].score,
            rerank_score=ranked.score,
            metadata=candidates[ranked.index].metadata,
        )
        for ranked in ranked_indices[:top_k]
    ]


@dataclass(frozen=True)
class ContextItem:
    source: ContextSource
    content: str
    rerank_score: float
    document_id: int | None = None
    document_version_id: int | None = None
    chunk_index: int | None = None
    session_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def retrieve_context(
    *,
    current_user: User,
    query: str,
    embedding_provider: EmbeddingProvider,
    vector_repository: VectorRepository,
    reranker: Reranker,
    top_k: int = DEFAULT_TOP_K,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    alpha: float = DEFAULT_ALPHA,
) -> list[ContextItem]:
    department_ids = [department.id for department in current_user.departments]

    stage_start = time.monotonic()
    query_vector = embedding_provider.embed_query(query)
    logger.debug("retrieve_context: embed_query took %.3fs", time.monotonic() - stage_start)

    stage_start = time.monotonic()
    doc_candidates = vector_repository.hybrid_search(
        query=query,
        query_vector=query_vector,
        owner_id=current_user.id,
        department_ids=department_ids,
        limit=candidate_limit,
        alpha=alpha,
    )
    logger.debug(
        "retrieve_context: hybrid_search took %.3fs (%d candidates)",
        time.monotonic() - stage_start,
        len(doc_candidates),
    )

    # Long-term memory (semantic recall of *other* past chat sessions) used
    # to be folded into this same candidate pool — removed: this is a
    # RAG-over-documents app, and searching the user's own chat history on
    # every message added a DB round-trip for a capability nobody wanted,
    # including a real multi-second stall whenever pool_pre_ping had to
    # silently reconnect to the remote Postgres instance. The chat_memory
    # table, summarization worker, and MemoryRepository interface are left
    # in place (see chat_service.delete_session) in case this comes back.
    combined: list[ContextItem] = [
        ContextItem(
            source="document",
            content=chunk.content,
            rerank_score=0.0,
            document_id=chunk.document_id,
            document_version_id=chunk.document_version_id,
            chunk_index=chunk.chunk_index,
            metadata=chunk.metadata,
        )
        for chunk in doc_candidates
    ]
    if not combined:
        return []

    stage_start = time.monotonic()
    ranked_indices = reranker.rerank(query, [item.content for item in combined])
    logger.debug("retrieve_context: rerank took %.3fs", time.monotonic() - stage_start)

    return [
        replace(combined[ranked.index], rerank_score=ranked.score)
        for ranked in ranked_indices[:top_k]
    ]
