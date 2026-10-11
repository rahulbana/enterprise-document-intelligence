# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Picks the configured LLMProvider implementation. Cached so client setup
# happens once per process, not once per request.

from functools import lru_cache

from app.core.config import settings
from app.providers.llm.base import LLMProvider
from app.providers.llm.ollama_provider import OllamaLLMProvider
from app.providers.llm.openai_provider import OpenAILLMProvider

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAILLMProvider,
    "ollama": OllamaLLMProvider,
}


@lru_cache
def get_llm_provider() -> LLMProvider:
    provider_cls = _PROVIDERS.get(settings.LLM_PROVIDER)
    if provider_cls is None:
        valid = ", ".join(sorted(_PROVIDERS))
        raise ValueError(f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'. Valid options: {valid}")
    return provider_cls()
