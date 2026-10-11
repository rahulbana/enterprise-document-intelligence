# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Picks the configured long-term MemoryRepository implementation. Cached so
# it's built once per process, not once per call.

from functools import lru_cache

from app.core.config import settings
from app.memory.long_term_base import MemoryRepository
from app.memory.sqlite_long_term_repository import SqliteMemoryRepository


@lru_cache
def get_memory_repository() -> MemoryRepository:
    if settings.MEMORY_BACKEND == "sqlite":
        return SqliteMemoryRepository()
    if settings.MEMORY_BACKEND == "weaviate":
        from app.vectorstore.client import get_weaviate_client
        from app.vectorstore.weaviate_memory_repository import WeaviateMemoryRepository

        return WeaviateMemoryRepository(get_weaviate_client())
    raise ValueError(
        f"Unknown MEMORY_BACKEND '{settings.MEMORY_BACKEND}'. Valid options: sqlite, weaviate"
    )
