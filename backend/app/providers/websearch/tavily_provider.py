# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# WebSearchProvider backed by Tavily's Search API — a plain REST call via
# httpx, same reasoning as CohereReranker: one endpoint, no need for a whole
# client SDK dependency.

import httpx

from app.core.config import settings
from app.providers.websearch.base import WebSearchProvider, WebSearchResponse, WebSearchResult

_SEARCH_URL = "https://api.tavily.com/search"


class TavilyWebSearchProvider(WebSearchProvider):
    def __init__(self, api_key: str | None = None, search_depth: str | None = None) -> None:
        self._api_key = api_key or settings.TAVILY_API_KEY
        if not self._api_key:
            raise ValueError("TAVILY_API_KEY is required when WEB_SEARCH_PROVIDER=tavily")
        self._search_depth = search_depth or settings.TAVILY_SEARCH_DEPTH

    def search(self, query: str, *, max_results: int) -> WebSearchResponse:
        response = httpx.post(
            _SEARCH_URL,
            json={
                "api_key": self._api_key,
                "query": query,
                "search_depth": self._search_depth,
                "max_results": max_results,
                # See WebSearchResponse.answer's docstring — raw snippets
                # alone were confirmed (in production) to miss the actual
                # answer for time-sensitive queries.
                "include_answer": True,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        results = [
            WebSearchResult(
                title=item.get("title") or item["url"],
                url=item["url"],
                content=item.get("content", ""),
            )
            for item in payload.get("results", [])
        ]
        return WebSearchResponse(results=results, answer=payload.get("answer") or None)
