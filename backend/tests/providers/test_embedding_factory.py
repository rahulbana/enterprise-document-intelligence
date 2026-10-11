# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Verifies the factory dispatches to the right provider class per
# EMBEDDING_PROVIDER setting, without downloading real models or hitting
# real network services.

import pytest

from app.core.config import settings
from app.providers.embeddings import factory as factory_module
from app.providers.embeddings.ollama_embeddings import OllamaEmbeddingProvider
from app.providers.embeddings.openai_embeddings import OpenAIEmbeddingProvider
from app.providers.embeddings.sentence_transformer_embeddings import (
    SentenceTransformerEmbeddingProvider,
)


@pytest.fixture(autouse=True)
def _clear_factory_cache():
    factory_module.get_embedding_provider.cache_clear()
    yield
    factory_module.get_embedding_provider.cache_clear()


def test_factory_returns_ollama_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "ollama")

    assert isinstance(factory_module.get_embedding_provider(), OllamaEmbeddingProvider)


def test_factory_returns_openai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    # OpenAI() raises at construction time if no API key is reachable, so the
    # SDK client is stubbed here too — this test dispatch shouldn't depend on
    # OPENAI_API_KEY being set in the environment.
    monkeypatch.setattr("app.providers.embeddings.openai_embeddings.OpenAI", lambda **_: object())
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")

    assert isinstance(factory_module.get_embedding_provider(), OpenAIEmbeddingProvider)


def test_factory_returns_sentence_transformer_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSentenceTransformer:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def get_sentence_embedding_dimension(self) -> int:
            return 768

    monkeypatch.setattr(
        "app.providers.embeddings.sentence_transformer_embeddings.SentenceTransformer",
        FakeSentenceTransformer,
    )
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "sentence_transformers")

    assert isinstance(factory_module.get_embedding_provider(), SentenceTransformerEmbeddingProvider)


def test_factory_raises_for_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "not-a-real-provider")

    with pytest.raises(ValueError, match="Unknown EMBEDDING_PROVIDER"):
        factory_module.get_embedding_provider()
