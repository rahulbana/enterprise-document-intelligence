# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# UserMemory collection definition. No vectorizer module configured, same as
# DocumentChunk — every summary's vector comes from our own
# EmbeddingProvider and is supplied on insert.

from weaviate.classes.config import Configure, DataType, Property
from weaviate.client import WeaviateClient

MEMORY_COLLECTION_NAME = "UserMemory"


def ensure_memory_schema(client: WeaviateClient) -> None:
    if client.collections.exists(MEMORY_COLLECTION_NAME):
        return

    client.collections.create(
        MEMORY_COLLECTION_NAME,
        vectorizer_config=Configure.Vectorizer.none(),
        properties=[
            Property(name="user_id", data_type=DataType.INT),
            Property(name="session_id", data_type=DataType.INT),
            Property(name="summary_text", data_type=DataType.TEXT),
            Property(name="covers_up_to_message_id", data_type=DataType.INT),
        ],
    )
