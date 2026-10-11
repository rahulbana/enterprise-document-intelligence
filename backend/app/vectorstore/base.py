# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# VectorRepository interface. replace_document_chunks is upsert-by-document:
# it atomically swaps out every chunk previously stored for a document for a
# fresh set, so only the currently active version's content is ever
# searchable. hybrid_search (Phase 4) is the read side: BM25+vector search
# scoped to what the requesting user is allowed to see.
#
# metadata (Phase 10): each chunk carries its source element's structural
# metadata (e.g. {"slide": 3, "kind": "notes"} or {"sheet": "Q1", "rows":
# [2, 18]}) — opaque to this layer, just stored and returned verbatim.

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: int
    document_version_id: int
    chunk_index: int
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorRepository(ABC):
    @abstractmethod
    def replace_document_chunks(
        self,
        *,
        document_id: int,
        document_version_id: int,
        owner_id: int,
        department_ids: list[int],
        chunks: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None: ...

    @abstractmethod
    def delete_document_chunks(self, document_id: int) -> None: ...

    @abstractmethod
    def get_document_chunks(self, document_id: int) -> list[RetrievedChunk]:
        """Every stored chunk for the document's active version, ordered by
        chunk_index ascending. Used to reconstruct a readable preview of the
        whole document (see document_service.get_document_preview) — not a
        search operation, so no query/scoring involved; score is always 0."""
        ...

    @abstractmethod
    def hybrid_search(
        self,
        *,
        query: str,
        query_vector: list[float],
        owner_id: int,
        department_ids: list[int],
        limit: int,
        alpha: float,
    ) -> list[RetrievedChunk]:
        """BM25+vector hybrid search, scoped to chunks whose active version is
        owned by owner_id or targets one of department_ids. alpha is
        Weaviate's blend factor: 0 = pure BM25, 1 = pure vector."""
        ...
