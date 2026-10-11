# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Picks the configured EmbeddingProvider implementation. Cached so the
# (potentially expensive-to-load, e.g. sentence-transformers) provider
# instance is built once per process, not once per call.

from functools import lru_cache

from app.core.config import settings
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.ollama_embeddings import OllamaEmbeddingProvider
from app.providers.embeddings.openai_embeddings import OpenAIEmbeddingProvider
from app.providers.embeddings.sentence_transformer_embeddings import (
    SentenceTransformerEmbeddingProvider,
)

_PROVIDERS: dict[str, type[EmbeddingProvider]] = {
    "ollama": OllamaEmbeddingProvider,
    "sentence_transformers": SentenceTransformerEmbeddingProvider,
    "openai": OpenAIEmbeddingProvider,
}


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    provider_cls = _PROVIDERS.get(settings.EMBEDDING_PROVIDER)
    if provider_cls is None:
        valid = ", ".join(sorted(_PROVIDERS))
        raise ValueError(
            f"Unknown EMBEDDING_PROVIDER '{settings.EMBEDDING_PROVIDER}'. Valid options: {valid}"
        )
    return provider_cls()
