# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Picks the configured ChunkingStrategy implementation — same
# registry-dict-plus-lru_cache pattern as get_embedding_provider().

from functools import lru_cache

from app.core.config import settings
from app.ingestion.chunking.base import ChunkingStrategy
from app.ingestion.chunking.fixed_size import FixedSizeChunkingStrategy
from app.ingestion.chunking.recursive import RecursiveChunkingStrategy
from app.ingestion.chunking.structure_aware import StructureAwareChunkingStrategy

_STRATEGIES: dict[str, type[ChunkingStrategy]] = {
    "fixed_size": FixedSizeChunkingStrategy,
    "recursive": RecursiveChunkingStrategy,
    "structure_aware": StructureAwareChunkingStrategy,
}


@lru_cache
def get_chunking_strategy() -> ChunkingStrategy:
    strategy_cls = _STRATEGIES.get(settings.CHUNKING_STRATEGY)
    if strategy_cls is None:
        valid = ", ".join(sorted(_STRATEGIES))
        raise ValueError(
            f"Unknown CHUNKING_STRATEGY '{settings.CHUNKING_STRATEGY}'. Valid options: {valid}"
        )
    return strategy_cls()
