# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Local reranker using a sentence-transformers CrossEncoder — no external
# service required. Default model is cross-encoder/ms-marco-MiniLM-L-6-v2.

from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.providers.reranker.base import RankedIndex, Reranker


class CrossEncoderReranker(Reranker):
    def __init__(self, model_name: str | None = None) -> None:
        self._model = CrossEncoder(
            model_name or settings.RERANKER_MODEL,
            local_files_only=settings.RERANKER_LOCAL_FILES_ONLY,
        )

    def rerank(self, query: str, documents: list[str]) -> list[RankedIndex]:
        if not documents:
            return []

        pairs = [(query, document) for document in documents]
        scores = self._model.predict(pairs)

        ranked = [
            RankedIndex(index=index, score=float(score)) for index, score in enumerate(scores)
        ]
        ranked.sort(key=lambda ranked_index: ranked_index.score, reverse=True)
        return ranked
