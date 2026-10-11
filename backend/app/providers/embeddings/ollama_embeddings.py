# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Embedding provider backed by a running Ollama server (default model:
# nomic-embed-text). Requires `ollama pull nomic-embed-text` on the host
# Ollama serves from.

import ollama

from app.core.config import settings
from app.providers.embeddings.base import EmbeddingProvider


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str | None = None) -> None:
        self._model = model_name or settings.OLLAMA_EMBEDDING_MODEL
        self._client = ollama.Client(host=settings.OLLAMA_BASE_URL)
        self._dimensions: int | None = None

    @property
    def dimensions(self) -> int:
        # Ollama has no static "describe model dimensions" call, so the first
        # access probes the model once and the result is cached for the life
        # of this provider instance.
        if self._dimensions is None:
            self._dimensions = len(self.embed_query("dimension probe"))
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"{settings.OLLAMA_EMBEDDING_DOCUMENT_PREFIX}{text}" for text in texts]
        response = self._client.embed(model=self._model, input=prefixed)
        return [list(embedding) for embedding in response.embeddings]

    def embed_query(self, text: str) -> list[float]:
        prefixed = f"{settings.OLLAMA_EMBEDDING_QUERY_PREFIX}{text}"
        response = self._client.embed(model=self._model, input=prefixed)
        return list(response.embeddings[0])
