# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Picks the configured Reranker implementation. Cached so the
# (expensive-to-load) cross-encoder model, or the Cohere client, is built
# once per process. Switchable via RERANKER_PROVIDER: "cross_encoder"
# (default, local, no external service) | "cohere" (hosted API, needs
# COHERE_API_KEY).

from functools import lru_cache

from app.core.config import settings
from app.providers.reranker.base import Reranker
from app.providers.reranker.cohere_reranker import CohereReranker
from app.providers.reranker.cross_encoder_reranker import CrossEncoderReranker

_PROVIDERS: dict[str, type[Reranker]] = {
    "cross_encoder": CrossEncoderReranker,
    "cohere": CohereReranker,
}


@lru_cache
def get_reranker() -> Reranker:
    provider_cls = _PROVIDERS.get(settings.RERANKER_PROVIDER)
    if provider_cls is None:
        valid = ", ".join(sorted(_PROVIDERS))
        raise ValueError(
            f"Unknown RERANKER_PROVIDER '{settings.RERANKER_PROVIDER}'. Valid options: {valid}"
        )
    return provider_cls()
