# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Builds the configured VectorRepository. Cached so the Weaviate connection
# (and its one-time schema check) happens once per process.

from functools import lru_cache

from app.vectorstore.base import VectorRepository
from app.vectorstore.client import get_weaviate_client
from app.vectorstore.weaviate_repository import WeaviateChunkRepository


@lru_cache
def get_vector_repository() -> VectorRepository:
    return WeaviateChunkRepository(get_weaviate_client())
