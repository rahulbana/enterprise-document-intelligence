# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Local embedding provider using sentence-transformers — no external service
# required. Default model is all-MiniLM-L6-v2 (symmetric, no instruction
# prefixes, no custom model code). Swapping in an asymmetric/custom-code
# model (e.g. nomic-ai/nomic-embed-text-v1.5) needs matching
# SENTENCE_TRANSFORMER_*_PREFIX values and TRUST_REMOTE_CODE=true.

from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.providers.embeddings.base import EmbeddingProvider


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str | None = None) -> None:
        self._model = SentenceTransformer(
            model_name or settings.SENTENCE_TRANSFORMER_EMBEDDING_MODEL,
            device=settings.SENTENCE_TRANSFORMER_DEVICE,
            trust_remote_code=settings.SENTENCE_TRANSFORMER_TRUST_REMOTE_CODE,
            local_files_only=settings.SENTENCE_TRANSFORMER_LOCAL_FILES_ONLY,
        )

    @property
    def dimensions(self) -> int:
        return self._model.get_sentence_embedding_dimension()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"{settings.SENTENCE_TRANSFORMER_DOCUMENT_PREFIX}{text}" for text in texts]
        embeddings = self._model.encode(prefixed, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        prefixed = f"{settings.SENTENCE_TRANSFORMER_QUERY_PREFIX}{text}"
        embedding = self._model.encode(prefixed, normalize_embeddings=True)
        return embedding.tolist()
