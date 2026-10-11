# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# VectorRepository implementation backed by Weaviate.

import json
from typing import Any

from weaviate.classes.data import DataObject
from weaviate.classes.query import Filter, MetadataQuery, Sort
from weaviate.client import WeaviateClient

from app.vectorstore.base import RetrievedChunk, VectorRepository
from app.vectorstore.schema import COLLECTION_NAME, ensure_schema

# Generous upper bound for the in-app preview pane — CHUNK_SIZE defaults to
# 1000 chars, so even a very long document stays well under this.
_MAX_PREVIEW_CHUNKS = 2000


class WeaviateChunkRepository(VectorRepository):
    def __init__(self, client: WeaviateClient) -> None:
        ensure_schema(client)
        self._client = client

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
    ) -> None:
        collection = self._client.collections.get(COLLECTION_NAME)
        collection.data.delete_many(where=Filter.by_property("document_id").equal(document_id))

        objects = [
            DataObject(
                properties={
                    "content": chunk,
                    "document_id": document_id,
                    "document_version_id": document_version_id,
                    "owner_id": owner_id,
                    "department_ids": department_ids,
                    "chunk_index": index,
                    "is_active_version": True,
                    "metadata_json": json.dumps(metadata),
                },
                vector=vector,
            )
            for index, (chunk, vector, metadata) in enumerate(
                zip(chunks, vectors, metadatas, strict=True)
            )
        ]
        if objects:
            collection.data.insert_many(objects)

    def delete_document_chunks(self, document_id: int) -> None:
        collection = self._client.collections.get(COLLECTION_NAME)
        collection.data.delete_many(where=Filter.by_property("document_id").equal(document_id))

    def get_document_chunks(self, document_id: int) -> list[RetrievedChunk]:
        collection = self._client.collections.get(COLLECTION_NAME)
        combined_filter = Filter.by_property("document_id").equal(
            document_id
        ) & Filter.by_property("is_active_version").equal(True)

        response = collection.query.fetch_objects(
            filters=combined_filter,
            sort=Sort.by_property("chunk_index", ascending=True),
            limit=_MAX_PREVIEW_CHUNKS,
        )

        results = []
        for obj in response.objects:
            raw_metadata = obj.properties.get("metadata_json")
            metadata = json.loads(raw_metadata) if raw_metadata else {}
            results.append(
                RetrievedChunk(
                    document_id=obj.properties["document_id"],
                    document_version_id=obj.properties["document_version_id"],
                    chunk_index=obj.properties["chunk_index"],
                    content=obj.properties["content"],
                    score=0.0,
                    metadata=metadata,
                )
            )
        return results

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
        collection = self._client.collections.get(COLLECTION_NAME)

        access_filter = Filter.by_property("owner_id").equal(owner_id)
        if department_ids:
            access_filter = access_filter | Filter.by_property("department_ids").contains_any(
                department_ids
            )
        combined_filter = Filter.by_property("is_active_version").equal(True) & access_filter

        response = collection.query.hybrid(
            query=query,
            vector=query_vector,
            alpha=alpha,
            limit=limit,
            filters=combined_filter,
            return_metadata=MetadataQuery(score=True),
        )

        results = []
        for obj in response.objects:
            raw_metadata = obj.properties.get("metadata_json")
            metadata = json.loads(raw_metadata) if raw_metadata else {}
            results.append(
                RetrievedChunk(
                    document_id=obj.properties["document_id"],
                    document_version_id=obj.properties["document_version_id"],
                    chunk_index=obj.properties["chunk_index"],
                    content=obj.properties["content"],
                    score=obj.metadata.score or 0.0,
                    metadata=metadata,
                )
            )
        return results
