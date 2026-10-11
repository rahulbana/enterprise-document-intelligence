# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# No live OpenAI call is made in tests; a fake client verifies the
# provider's own logic (no prefixing, response shape, dimension probing).

from dataclasses import dataclass, field

import pytest

from app.providers.embeddings import openai_embeddings as module
from app.providers.embeddings.openai_embeddings import OpenAIEmbeddingProvider


@dataclass
class FakeEmbeddingItem:
    embedding: list[float]


@dataclass
class FakeEmbeddingsResponse:
    data: list[FakeEmbeddingItem]


@dataclass
class FakeEmbeddingsResource:
    calls: list[tuple[str, list[str]]] = field(default_factory=list)

    def create(self, model: str, input: list[str]) -> FakeEmbeddingsResponse:
        self.calls.append((model, input))
        return FakeEmbeddingsResponse([FakeEmbeddingItem([1.0, 2.0]) for _ in input])


class FakeOpenAIClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.embeddings = FakeEmbeddingsResource()


def test_embed_documents_sends_texts_unmodified(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "OpenAI", FakeOpenAIClient)
    provider = OpenAIEmbeddingProvider()

    result = provider.embed_documents(["hello", "world"])

    assert provider._client.embeddings.calls[-1] == (
        "text-embedding-3-small",
        ["hello", "world"],
    )
    assert result == [[1.0, 2.0], [1.0, 2.0]]


def test_embed_query_delegates_to_embed_documents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "OpenAI", FakeOpenAIClient)
    provider = OpenAIEmbeddingProvider()

    assert provider.embed_query("hello") == [1.0, 2.0]


def test_dimensions_probes_once_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "OpenAI", FakeOpenAIClient)
    provider = OpenAIEmbeddingProvider()

    assert provider.dimensions == 2
    assert provider.dimensions == 2
    assert len(provider._client.embeddings.calls) == 1
