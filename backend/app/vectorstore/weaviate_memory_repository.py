# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# MemoryRepository implementation backed by Weaviate. One object per
# session_id: upsert_summary always deletes-then-inserts, same idiom as
# WeaviateChunkRepository.replace_document_chunks, so there's never more
# than one rolling summary per session.

from weaviate.classes.query import Filter, MetadataQuery
from weaviate.client import WeaviateClient

from app.memory.long_term_base import MemoryRepository, RetrievedMemory, StoredSummary
from app.vectorstore.memory_schema import MEMORY_COLLECTION_NAME, ensure_memory_schema


class WeaviateMemoryRepository(MemoryRepository):
    def __init__(self, client: WeaviateClient) -> None:
        ensure_memory_schema(client)
        self._client = client

    def get_summary(self, session_id: int) -> StoredSummary | None:
        collection = self._client.collections.get(MEMORY_COLLECTION_NAME)
        response = collection.query.fetch_objects(
            filters=Filter.by_property("session_id").equal(session_id), limit=1
        )
        if not response.objects:
            return None
        obj = response.objects[0]
        return StoredSummary(
            session_id=obj.properties["session_id"],
            summary_text=obj.properties["summary_text"],
            covers_up_to_message_id=obj.properties["covers_up_to_message_id"],
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
        collection = self._client.collections.get(MEMORY_COLLECTION_NAME)
        collection.data.delete_many(where=Filter.by_property("session_id").equal(session_id))
        collection.data.insert(
            properties={
                "user_id": user_id,
                "session_id": session_id,
                "summary_text": summary_text,
                "covers_up_to_message_id": covers_up_to_message_id,
            },
            vector=vector,
        )

    def delete_summary(self, session_id: int) -> None:
        collection = self._client.collections.get(MEMORY_COLLECTION_NAME)
        collection.data.delete_many(where=Filter.by_property("session_id").equal(session_id))

    def search_memories(
        self, *, user_id: int, query_vector: list[float], limit: int
    ) -> list[RetrievedMemory]:
        collection = self._client.collections.get(MEMORY_COLLECTION_NAME)
        response = collection.query.near_vector(
            near_vector=query_vector,
            limit=limit,
            filters=Filter.by_property("user_id").equal(user_id),
            return_metadata=MetadataQuery(certainty=True),
        )
        return [
            RetrievedMemory(
                session_id=obj.properties["session_id"],
                summary_text=obj.properties["summary_text"],
                score=obj.metadata.certainty or 0.0,
            )
            for obj in response.objects
        ]
