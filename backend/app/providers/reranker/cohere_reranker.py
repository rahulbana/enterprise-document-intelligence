# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Reranker backed by Cohere's hosted Rerank API — an alternative to the
# local cross-encoder for deployments that would rather call a managed
# service than load a model into the app process. A plain REST call via
# httpx rather than the `cohere` SDK: one endpoint, no need for a whole
# client library dependency.

import httpx

from app.core.config import settings
from app.providers.reranker.base import RankedIndex, Reranker

_RERANK_URL = "https://api.cohere.com/v1/rerank"


class CohereReranker(Reranker):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or settings.COHERE_API_KEY
        if not self._api_key:
            raise ValueError("COHERE_API_KEY is required when RERANKER_PROVIDER=cohere")
        self._model = model or settings.COHERE_RERANK_MODEL

    def rerank(self, query: str, documents: list[str]) -> list[RankedIndex]:
        if not documents:
            return []

        response = httpx.post(
            _RERANK_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self._model, "query": query, "documents": documents},
            timeout=30,
        )
        response.raise_for_status()

        ranked = [
            RankedIndex(index=item["index"], score=item["relevance_score"])
            for item in response.json()["results"]
        ]
        # Cohere's API already returns results sorted best-first, but sort
        # explicitly anyway — matches CrossEncoderReranker and keeps the
        # contract enforced here rather than trusted from the response.
        ranked.sort(key=lambda ranked_index: ranked_index.score, reverse=True)
        return ranked
