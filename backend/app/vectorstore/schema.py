# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# DocumentChunk collection definition. No vectorizer module is configured
# (matches docker-compose's DEFAULT_VECTORIZER_MODULE=none) — every chunk's
# vector comes from our own EmbeddingProvider and is supplied on insert.

from weaviate.classes.config import Configure, DataType, Property
from weaviate.client import WeaviateClient

COLLECTION_NAME = "DocumentChunk"


def ensure_schema(client: WeaviateClient) -> None:
    if client.collections.exists(COLLECTION_NAME):
        # Phase 10 added metadata_json to a collection that may already
        # exist (e.g. this app's own Weaviate Cloud instance from earlier
        # phases) — patch it in rather than requiring a manual migration.
        collection = client.collections.get(COLLECTION_NAME)
        existing_properties = {prop.name for prop in collection.config.get().properties}
        if "metadata_json" not in existing_properties:
            collection.config.add_property(Property(name="metadata_json", data_type=DataType.TEXT))
        return

    client.collections.create(
        COLLECTION_NAME,
        vectorizer_config=Configure.Vectorizer.none(),
        properties=[
            Property(name="content", data_type=DataType.TEXT),
            Property(name="document_id", data_type=DataType.INT),
            Property(name="document_version_id", data_type=DataType.INT),
            Property(name="owner_id", data_type=DataType.INT),
            Property(name="department_ids", data_type=DataType.INT_ARRAY),
            Property(name="chunk_index", data_type=DataType.INT),
            Property(name="is_active_version", data_type=DataType.BOOL),
            # JSON-serialized structural metadata (Phase 10) — e.g. page,
            # slide/sheet number, table bounds. Opaque to Weaviate; only the
            # app interprets it.
            Property(name="metadata_json", data_type=DataType.TEXT),
        ],
    )
