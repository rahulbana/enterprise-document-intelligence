# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# No live Ollama server is used in tests; a fake client verifies the
# provider's own logic (prefixing, response shape, dimension probing).

from dataclasses import dataclass, field

import pytest

from app.providers.embeddings import ollama_embeddings as module
from app.providers.embeddings.ollama_embeddings import OllamaEmbeddingProvider


@dataclass
class FakeEmbedResponse:
    embeddings: list[list[float]]


@dataclass
class FakeOllamaClient:
    host: str | None = None
    calls: list[tuple[str, str | list[str]]] = field(default_factory=list)

    def embed(self, model: str, input: str | list[str]) -> FakeEmbedResponse:
        self.calls.append((model, input))
        if isinstance(input, str):
            return FakeEmbedResponse([[1.0, 2.0]])
        return FakeEmbedResponse([[1.0, 2.0] for _ in input])


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeOllamaClient:
    fake = FakeOllamaClient()
    monkeypatch.setattr(module.ollama, "Client", lambda host=None: fake)
    return fake


def test_embed_documents_applies_document_prefix(fake_client: FakeOllamaClient) -> None:
    provider = OllamaEmbeddingProvider()

    result = provider.embed_documents(["hello"])

    assert fake_client.calls[-1] == ("nomic-embed-text", ["search_document: hello"])
    assert result == [[1.0, 2.0]]


def test_embed_query_applies_query_prefix(fake_client: FakeOllamaClient) -> None:
    provider = OllamaEmbeddingProvider()

    result = provider.embed_query("hello")

    assert fake_client.calls[-1] == ("nomic-embed-text", "search_query: hello")
    assert result == [1.0, 2.0]


def test_dimensions_probes_once_and_caches(fake_client: FakeOllamaClient) -> None:
    provider = OllamaEmbeddingProvider()

    assert provider.dimensions == 2
    assert provider.dimensions == 2
    assert len(fake_client.calls) == 1
