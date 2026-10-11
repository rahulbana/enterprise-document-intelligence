# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# No live Cohere call is made in tests; httpx.post is stubbed to verify the
# provider's own logic (request shape, auth header, response parsing, and
# the defensive re-sort).

from dataclasses import dataclass, field

import pytest

from app.providers.reranker import cohere_reranker as module
from app.providers.reranker.cohere_reranker import CohereReranker


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


def test_rerank_parses_and_sorts_results_best_first(monkeypatch: pytest.MonkeyPatch) -> None:
    # Deliberately out of score order in the fake response — the provider
    # must sort itself rather than trust the API's ordering.
    fake_post = FakePost(
        FakeResponse(
            {
                "results": [
                    {"index": 1, "relevance_score": 0.2},
                    {"index": 0, "relevance_score": 0.9},
                ]
            }
        )
    )
    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = CohereReranker(api_key="test-key")

    ranked = provider.rerank("query", ["doc a", "doc b"])

    assert [r.index for r in ranked] == [0, 1]
    assert ranked[0].score == 0.9


def test_rerank_sends_model_query_documents_and_auth_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_post = FakePost(FakeResponse({"results": []}))
    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = CohereReranker(api_key="test-key", model="rerank-v3.5")

    provider.rerank("what is RAG?", ["doc a", "doc b"])

    (args, kwargs) = fake_post.calls[0]
    assert args[0] == "https://api.cohere.com/v1/rerank"
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"] == {
        "model": "rerank-v3.5",
        "query": "what is RAG?",
        "documents": ["doc a", "doc b"],
    }


def test_rerank_empty_documents_skips_the_http_call(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_post = FakePost(FakeResponse({"results": []}))
    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = CohereReranker(api_key="test-key")

    assert provider.rerank("query", []) == []
    assert fake_post.calls == []


def test_missing_api_key_raises() -> None:
    with pytest.raises(ValueError, match="COHERE_API_KEY"):
        CohereReranker(api_key=None)


def test_rerank_propagates_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class BoomError(Exception):
        pass

    fake_post = FakePost(FakeResponse({}, status_error=BoomError("rate limited")))
    monkeypatch.setattr(module.httpx, "post", fake_post)
    provider = CohereReranker(api_key="test-key")

    with pytest.raises(BoomError):
        provider.rerank("query", ["doc a"])
