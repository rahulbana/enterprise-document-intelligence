# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# No live Tavily call is made in tests; httpx.post is stubbed to verify the
# provider's own logic (request shape, response parsing, missing-title
# fallback).

from dataclasses import dataclass, field

import pytest

from app.providers.websearch import tavily_provider as module
from app.providers.websearch.tavily_provider import TavilyWebSearchProvider


@dataclass
class FakeResponse:
    payload: dict
    status_error: Exception | None = None

    def raise_for_status(self) -> None:
        if self.status_error:
            raise self.status_error

    def json(self) -> dict:
        return self.payload


@dataclass
class FakePost:
    response: FakeResponse
    calls: list[tuple[tuple, dict]] = field(default_factory=list)

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


def test_search_parses_results(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_post = FakePost(
        FakeResponse(
            {
                "results": [
                    {"title": "Example", "url": "https://example.com/a", "content": "Snippet A"},
                    {"title": "Other", "url": "https://example.com/b", "content": "Snippet B"},
                ]
            }
        )
    )
    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = TavilyWebSearchProvider(api_key="test-key")

    response = provider.search("query", max_results=5)

    assert [r.title for r in response.results] == ["Example", "Other"]
    assert [r.url for r in response.results] == ["https://example.com/a", "https://example.com/b"]
    assert [r.content for r in response.results] == ["Snippet A", "Snippet B"]


def test_search_falls_back_to_url_when_title_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_post = FakePost(
        FakeResponse({"results": [{"url": "https://example.com/no-title", "content": "x"}]})
    )
    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = TavilyWebSearchProvider(api_key="test-key")

    response = provider.search("query", max_results=5)

    assert response.results[0].title == "https://example.com/no-title"


def test_search_sends_api_key_query_depth_and_max_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_post = FakePost(FakeResponse({"results": []}))
    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = TavilyWebSearchProvider(api_key="test-key", search_depth="advanced")

    provider.search("what is RAG?", max_results=3)

    (args, kwargs) = fake_post.calls[0]
    assert args[0] == "https://api.tavily.com/search"
    assert kwargs["json"] == {
        "api_key": "test-key",
        "query": "what is RAG?",
        "search_depth": "advanced",
        "max_results": 3,
        "include_answer": True,
    }


def test_search_parses_synthesized_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_post = FakePost(FakeResponse({"results": [], "answer": "Donald Trump is president."}))
    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = TavilyWebSearchProvider(api_key="test-key")

    response = provider.search("query", max_results=5)

    assert response.answer == "Donald Trump is president."


def test_search_answer_is_none_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_post = FakePost(FakeResponse({"results": []}))
    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = TavilyWebSearchProvider(api_key="test-key")

    response = provider.search("query", max_results=5)

    assert response.answer is None


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module.settings, "TAVILY_API_KEY", None)
    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        TavilyWebSearchProvider(api_key=None)


def test_search_propagates_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class BoomError(Exception):
        pass

    fake_post = FakePost(FakeResponse({}, status_error=BoomError("rate limited")))
    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = TavilyWebSearchProvider(api_key="test-key")

    with pytest.raises(BoomError):
        provider.search("query", max_results=5)
