# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Fake EmbeddingProvider/VectorRepository/Reranker/LLMProvider for tests —
# deterministic, no network, no real Weaviate/cross-encoder/LLM. Used both
# directly (unit tests) and wired into the test client's ingestion enqueuer
# (integration tests), so the full upload -> ingest -> ready -> retrieve ->
# chat pipeline is exercised without any live service.

from collections.abc import Iterator

from app.memory.long_term_base import MemoryRepository, RetrievedMemory, StoredSummary
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider, ToolCallRequest
from app.providers.reranker.base import RankedIndex, Reranker
from app.providers.websearch.base import WebSearchProvider, WebSearchResponse, WebSearchResult
from app.vectorstore.base import RetrievedChunk, VectorRepository

FAKE_EMBEDDING_DIMENSIONS = 8


class FakeEmbeddingProvider(EmbeddingProvider):
    @property
    def dimensions(self) -> int:
        return FAKE_EMBEDDING_DIMENSIONS

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    @staticmethod
    def _embed(text: str) -> list[float]:
        # Deterministic and cheap: derive a fixed-length vector from the
        # text's length so different chunks get different (fake) vectors.
        base = float(len(text) % 100) / 100.0
        return [base + i * 0.01 for i in range(FAKE_EMBEDDING_DIMENSIONS)]


class FakeVectorRepository(VectorRepository):
    def __init__(self) -> None:
        self.replace_calls: list[dict] = []
        self.delete_calls: list[int] = []
        self._stored: dict[int, dict] = {}  # document_id -> replace_document_chunks kwargs

    def replace_document_chunks(
        self,
        *,
        document_id: int,
        document_version_id: int,
        owner_id: int,
        department_ids: list[int],
        chunks: list[str],
        vectors: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        self.replace_calls.append(
            {
                "document_id": document_id,
                "document_version_id": document_version_id,
                "owner_id": owner_id,
                "department_ids": department_ids,
                "chunks": chunks,
                "vectors": vectors,
                "metadatas": metadatas,
            }
        )
        self._stored[document_id] = {
            "document_version_id": document_version_id,
            "owner_id": owner_id,
            "department_ids": department_ids,
            "chunks": chunks,
            "metadatas": metadatas,
        }

    def delete_document_chunks(self, document_id: int) -> None:
        self.delete_calls.append(document_id)
        self._stored.pop(document_id, None)

    def get_document_chunks(self, document_id: int) -> list[RetrievedChunk]:
        stored = self._stored.get(document_id)
        if stored is None:
            return []
        return [
            RetrievedChunk(
                document_id=document_id,
                document_version_id=stored["document_version_id"],
                chunk_index=index,
                content=chunk,
                score=0.0,
                metadata=stored["metadatas"][index],
            )
            for index, chunk in enumerate(stored["chunks"])
        ]

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
        query_words = set(query.lower().split())
        candidates: list[RetrievedChunk] = []
        for document_id, stored in self._stored.items():
            is_owner = stored["owner_id"] == owner_id
            in_department = bool(set(stored["department_ids"]) & set(department_ids))
            if not (is_owner or in_department):
                continue
            for chunk_index, chunk in enumerate(stored["chunks"]):
                overlap = len(query_words & set(chunk.lower().split()))
                candidates.append(
                    RetrievedChunk(
                        document_id=document_id,
                        document_version_id=stored["document_version_id"],
                        chunk_index=chunk_index,
                        content=chunk,
                        score=float(overlap),
                        metadata=stored["metadatas"][chunk_index],
                    )
                )
        candidates.sort(key=lambda c: (-c.score, c.document_id, c.chunk_index))
        return candidates[:limit]


class FakeReranker(Reranker):
    """Preserves the input order (position-based score) — deterministic and
    dependency-free, so tests can assert on ordering without a real
    cross-encoder model."""

    def rerank(self, query: str, documents: list[str]) -> list[RankedIndex]:
        count = len(documents)
        return [RankedIndex(index=i, score=float(count - i)) for i in range(count)]


class FakeMemoryRepository(MemoryRepository):
    def __init__(self) -> None:
        self._summaries: dict[int, dict] = {}  # session_id -> summary fields

    def get_summary(self, session_id: int) -> StoredSummary | None:
        stored = self._summaries.get(session_id)
        if stored is None:
            return None
        return StoredSummary(
            session_id=session_id,
            summary_text=stored["summary_text"],
            covers_up_to_message_id=stored["covers_up_to_message_id"],
        )

    def upsert_summary(
        self,
        *,
        user_id: int,
        session_id: int,
        summary_text: str,
        vector: list[float],
        covers_up_to_message_id: int,
    ) -> None:
        self._summaries[session_id] = {
            "user_id": user_id,
            "summary_text": summary_text,
            "vector": vector,
            "covers_up_to_message_id": covers_up_to_message_id,
        }

    def delete_summary(self, session_id: int) -> None:
        self._summaries.pop(session_id, None)

    def search_memories(
        self, *, user_id: int, query_vector: list[float], limit: int
    ) -> list[RetrievedMemory]:
        candidates = [
            RetrievedMemory(session_id=session_id, summary_text=stored["summary_text"], score=1.0)
            for session_id, stored in self._summaries.items()
            if stored["user_id"] == user_id
        ]
        return candidates[:limit]


class FakeLLMProvider(LLMProvider):
    """Yields a fixed, deterministic reply split into a few word-sized
    tokens, so tests can assert on streaming behavior (multiple chunks)
    without a real model. Records every call's messages (and the tools it
    was offered) for inspection.

    Set tool_calls_to_request to simulate the model calling a tool instead
    of answering, for the first `tool_call_hops` calls in a turn (mimics
    OpenAI's finish_reason=tool_calls) — every call after that answers
    normally with `reply`, so chat_service's multi-hop tool-calling loop
    behaves like a real model that eventually has its answer. Default
    tool_call_hops=1 mimics a single-hop tool call.
    """

    def __init__(self, reply: str = "This is a fake answer.") -> None:
        self.reply = reply
        self.calls: list[list[dict[str, str]]] = []
        self.tools_received: list[list[dict] | None] = []
        self.tool_calls_to_request: list[ToolCallRequest] | None = None
        self.tool_call_hops: int = 1
        # request_tool_call (citation grounding): None reproduces the base
        # class's real default ("provider doesn't support forced tool
        # calls"), so tests that don't care about grounding see it degrade
        # to unfiltered citations, same as every test written before
        # grounding existed. Set this to script a grounding response.
        self.tool_call_response: ToolCallRequest | None = None
        self.tool_call_requests: list[tuple[list[dict[str, str]], dict]] = []

    def stream_chat(
        self, messages: list[dict[str, str]], *, tools: list[dict] | None = None
    ) -> Iterator[str | list[ToolCallRequest]]:
        self.calls.append(messages)
        self.tools_received.append(tools)
        if self.tool_calls_to_request is not None and len(self.calls) <= self.tool_call_hops:
            yield self.tool_calls_to_request
            return
        for word in self.reply.split(" "):
            yield word + " "

    def request_tool_call(self, messages: list[dict[str, str]], tool: dict) -> ToolCallRequest | None:
        self.tool_call_requests.append((messages, tool))
        return self.tool_call_response


class FakeWebSearchProvider(WebSearchProvider):
    def __init__(self, results: list[WebSearchResult] | None = None, answer: str | None = None) -> None:
        self.results = results if results is not None else []
        self.answer = answer
        self.calls: list[tuple[str, int]] = []  # (query, max_results)

    def search(self, query: str, *, max_results: int) -> WebSearchResponse:
        self.calls.append((query, max_results))
        return WebSearchResponse(results=self.results, answer=self.answer)
