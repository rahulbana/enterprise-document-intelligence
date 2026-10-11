# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Picks the configured WebSearchProvider — or None. Unlike the other
# provider factories (embeddings/LLM/reranker), which raise on
# misconfiguration because the app can't function without them, web search
# is optional and additive: a chat request works fine without it (the model
# just never gets offered the tool), so a missing/invalid setup here
# degrades to "no web search" with a log line instead of failing every chat
# request over a feature nobody may have set up yet.

import logging
from functools import lru_cache

from app.core.config import settings
from app.providers.websearch.base import WebSearchProvider
from app.providers.websearch.tavily_provider import TavilyWebSearchProvider

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, type[WebSearchProvider]] = {
    "tavily": TavilyWebSearchProvider,
}


@lru_cache
def get_web_search_provider() -> WebSearchProvider | None:
    if not settings.WEB_SEARCH_ENABLED:
        return None

    provider_cls = _PROVIDERS.get(settings.WEB_SEARCH_PROVIDER)
    if provider_cls is None:
        valid = ", ".join(sorted(_PROVIDERS))
        logger.warning(
            "Unknown WEB_SEARCH_PROVIDER '%s' (valid: %s) — web_search tool disabled",
            settings.WEB_SEARCH_PROVIDER,
            valid,
        )
        return None

    try:
        return provider_cls()
    except ValueError:
        logger.warning(
            "WEB_SEARCH_PROVIDER=%s is missing required configuration (e.g. an API "
            "key) — web_search tool disabled",
            settings.WEB_SEARCH_PROVIDER,
        )
        return None
