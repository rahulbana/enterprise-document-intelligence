# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# MemoryRepository implementation backed by the app's own SQLite/Postgres
# database (a plain table, not a vector index) — the default for now since
# it needs no separate service. search_memories does brute-force cosine
# similarity in Python: fine at this scale (one row per chat session per
# user), and swappable later for a real vector store (see
# WeaviateMemoryRepository) behind the same interface without touching
# callers.

import math
from datetime import UTC, datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from app.db.session import SessionLocal
from app.memory.long_term_base import MemoryRepository, RetrievedMemory, StoredSummary
from app.models.chat_memory import ChatMemory


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SqliteMemoryRepository(MemoryRepository):
    def get_summary(self, session_id: int) -> StoredSummary | None:
        db = SessionLocal()
        try:
            row = db.scalar(select(ChatMemory).where(ChatMemory.session_id == session_id))
        finally:
            db.close()
        if row is None:
            return None
        return StoredSummary(
            session_id=row.session_id,
            summary_text=row.summary_text,
            covers_up_to_message_id=row.covers_up_to_message_id,
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
        db = SessionLocal()
        try:
            row = db.scalar(select(ChatMemory).where(ChatMemory.session_id == session_id))
            if row is None:
                row = ChatMemory(session_id=session_id, user_id=user_id)
                db.add(row)
            row.user_id = user_id
            row.summary_text = summary_text
            row.vector_json = vector
            row.covers_up_to_message_id = covers_up_to_message_id
            row.updated_at = datetime.now(UTC)
            db.commit()
        finally:
            db.close()

    def delete_summary(self, session_id: int) -> None:
        db = SessionLocal()
        try:
            db.execute(sa_delete(ChatMemory).where(ChatMemory.session_id == session_id))
            db.commit()
        finally:
            db.close()

    def search_memories(
        self, *, user_id: int, query_vector: list[float], limit: int
    ) -> list[RetrievedMemory]:
        db = SessionLocal()
        try:
            rows = db.scalars(select(ChatMemory).where(ChatMemory.user_id == user_id)).all()
        finally:
            db.close()

        scored = [
            RetrievedMemory(
                session_id=row.session_id,
                summary_text=row.summary_text,
                score=_cosine_similarity(query_vector, row.vector_json),
            )
            for row in rows
        ]
        scored.sort(key=lambda memory: memory.score, reverse=True)
        return scored[:limit]
