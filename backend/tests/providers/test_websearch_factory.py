# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Verifies the web search factory's degrade-to-None behavior — unlike the
# other provider factories (embeddings/LLM/reranker), which raise on
# misconfiguration, this one is optional/additive and must never break chat
# over it (see factory.py's docstring).

import pytest

from app.core.config import settings
from app.providers.websearch import factory as factory_module
from app.providers.websearch.tavily_provider import TavilyWebSearchProvider


@pytest.fixture(autouse=True)
def _clear_factory_cache():
    factory_module.get_web_search_provider.cache_clear()
    yield
    factory_module.get_web_search_provider.cache_clear()


def test_factory_returns_tavily_provider_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-key")

    assert isinstance(factory_module.get_web_search_provider(), TavilyWebSearchProvider)


def test_factory_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", False)
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "test-key")

    assert factory_module.get_web_search_provider() is None


def test_factory_returns_none_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr(settings, "TAVILY_API_KEY", None)

    assert factory_module.get_web_search_provider() is None


def test_factory_returns_none_for_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "not-a-real-provider")

    assert factory_module.get_web_search_provider() is None
