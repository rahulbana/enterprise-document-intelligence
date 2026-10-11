# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# WebSearchProvider interface — the web_search chat tool (see
# chat_service.py) calls this, not Tavily (or whichever provider) directly,
# so a second provider slots in later without touching the tool-calling
# plumbing. Mirrors the Reranker/EmbeddingProvider pluggable-interface
# pattern already used elsewhere in this codebase.

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    content: str  # snippet/summary the search API returned, not the full page


@dataclass(frozen=True)
class WebSearchResponse:
    results: list[WebSearchResult] = field(default_factory=list)
    # A synthesized direct answer, when the provider offers one (Tavily's
    # include_answer). Matters more than it sounds: raw snippets for a
    # time-sensitive query ("who is the current president") are often
    # reference/historical pages that never actually state the current
    # answer in their snippet text — a model given only those snippets can
    # (and, observed in production, did) fall back to its own stale training
    # knowledge instead. A synthesized answer is generated *for* the query,
    # not just retrieved as a matching page, so it reliably contains the
    # thing that was actually asked.
    answer: str | None = None


class WebSearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, *, max_results: int) -> WebSearchResponse:
        """Best-effort web search — return whatever's available. Callers
        (chat_service) treat an empty response and a raised exception the
        same way (no results), so implementations should raise on a genuine
        failure rather than silently returning an empty WebSearchResponse
        themselves."""
        ...
