# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# MemoryRepository interface — long-term chat memory (Phase 6). One rolling
# summary object per chat session: each summarization run replaces it with a
# new summary that folds in the previous one plus whatever turns have fallen
# out of the short-term window since. Private to the session's owner, same
# as chat itself (no department sharing).
#
# Deliberately doesn't take a db: Session — same reasoning as
# VectorRepository: implementations own their storage connection (a second
# SQLite session, a Weaviate client, ...) rather than sharing the caller's
# request-scoped one, since memory writes are best-effort/eventual, not
# transactional with the chat reply that triggered them.

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedMemory:
    session_id: int
    summary_text: str
    score: float


@dataclass(frozen=True)
class StoredSummary:
    session_id: int
    summary_text: str
    covers_up_to_message_id: int


class MemoryRepository(ABC):
    @abstractmethod
    def get_summary(self, session_id: int) -> StoredSummary | None:
        """The current rolling summary for a session, or None if it hasn't
        been summarized yet."""
        ...

    @abstractmethod
    def upsert_summary(
        self,
        *,
        user_id: int,
        session_id: int,
        summary_text: str,
        vector: list[float],
        covers_up_to_message_id: int,
    ) -> None: ...

    @abstractmethod
    def delete_summary(self, session_id: int) -> None: ...

    @abstractmethod
    def search_memories(
        self, *, user_id: int, query_vector: list[float], limit: int
    ) -> list[RetrievedMemory]:
        """Vector search over a user's own rolling summaries only — memories
        aren't shared across users."""
        ...
