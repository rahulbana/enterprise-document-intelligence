# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Verifies the factory dispatches to the right reranker class per
# RERANKER_PROVIDER setting, without loading the real cross-encoder model
# or requiring a real COHERE_API_KEY.

import pytest

from app.core.config import settings
from app.providers.reranker import factory as factory_module
from app.providers.reranker.cohere_reranker import CohereReranker
from app.providers.reranker.cross_encoder_reranker import CrossEncoderReranker


@pytest.fixture(autouse=True)
def _clear_factory_cache():
    factory_module.get_reranker.cache_clear()
    yield
    factory_module.get_reranker.cache_clear()


def test_factory_returns_cross_encoder_reranker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.providers.reranker.cross_encoder_reranker.CrossEncoder", lambda *_a, **_k: object()
    )
    monkeypatch.setattr(settings, "RERANKER_PROVIDER", "cross_encoder")

    assert isinstance(factory_module.get_reranker(), CrossEncoderReranker)


def test_factory_returns_cohere_reranker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RERANKER_PROVIDER", "cohere")
    monkeypatch.setattr(settings, "COHERE_API_KEY", "test-key")

    assert isinstance(factory_module.get_reranker(), CohereReranker)


def test_factory_raises_for_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RERANKER_PROVIDER", "not-a-real-provider")

    with pytest.raises(ValueError, match="Unknown RERANKER_PROVIDER"):
        factory_module.get_reranker()
