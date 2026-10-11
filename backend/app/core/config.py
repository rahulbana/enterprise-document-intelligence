# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Central application settings, loaded once from environment / .env.

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "Document Intelligence"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    # "text" (default, human-readable) or "json" (one object per line, for
    # log aggregators) — see app/core/logging.py.
    LOG_FORMAT: str = "text"
    # Comma-separated in .env (e.g. "http://localhost:5173,http://localhost:3000");
    # kept as a plain str field so pydantic-settings doesn't try to JSON-parse it.
    CORS_ORIGINS: str = "http://localhost:5173"

    # Auth
    SECRET_KEY: str = "change-me-to-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # Database. Pool settings only apply for non-SQLite (Postgres, Phase 8) —
    # see app/db/session.py.
    DATABASE_URL: str = "sqlite:///./document_intelligence.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE_SECONDS: int = 1800

    # Redis / Celery. When false, uploads skip enqueueing an ingestion task
    # entirely (versions stay PENDING) instead of trying to reach Redis —
    # for dev without Redis/Celery running yet.
    CELERY_ENABLED: bool = True
    REDIS_URL: str = "redis://localhost:6379/0"

    # Weaviate
    WEAVIATE_URL: str = "http://localhost:8080"
    WEAVIATE_GRPC_PORT: int = 50051
    WEAVIATE_API_KEY: str | None = None

    # Ingestion (Phase 3): chunk_size/chunk_overlap are character budgets
    # shared by every strategy below, not hard limits.
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150

    # Chunking strategy (Phase 11): "fixed_size" (default, word-packing —
    # unchanged since Phase 3) | "recursive" (splits on paragraph/sentence
    # boundaries first, falls back to word-packing only where a segment has
    # no smaller boundary to split on — better prose coherence) |
    # "structure_aware" (routes each element by its parser-assigned kind:
    # table/sheet elements are packed whole-line so a chunk never cuts a row
    # in half, everything else goes through "recursive").
    CHUNKING_STRATEGY: str = "fixed_size"

    # File storage
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "./storage"

    # LLM provider
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str | None = None
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_CHAT_MODEL: str = "llama3.1"

    # Embedding provider: "ollama" | "sentence_transformers" | "openai"
    EMBEDDING_PROVIDER: str = "ollama"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Ollama's default model (nomic-embed-text) is asymmetric: queries and
    # documents need different instruction prefixes for good retrieval.
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_EMBEDDING_QUERY_PREFIX: str = "search_query: "
    OLLAMA_EMBEDDING_DOCUMENT_PREFIX: str = "search_document: "

    # sentence-transformers' default model (all-MiniLM-L6-v2) is symmetric,
    # so its prefixes default to empty and it needs no custom model code.
    # If you swap in an asymmetric/custom-code model (e.g.
    # nomic-ai/nomic-embed-text-v1.5), set matching prefixes below and flip
    # SENTENCE_TRANSFORMER_TRUST_REMOTE_CODE=true (only for a model source
    # you trust — it executes code shipped in the model repo).
    SENTENCE_TRANSFORMER_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    SENTENCE_TRANSFORMER_DEVICE: str = "cpu"
    SENTENCE_TRANSFORMER_TRUST_REMOTE_CODE: bool = False
    SENTENCE_TRANSFORMER_QUERY_PREFIX: str = ""
    SENTENCE_TRANSFORMER_DOCUMENT_PREFIX: str = ""
    # True (default): never phone home to check for a newer version of the
    # model — use whatever's already in the local HF cache, or fail loudly
    # if it isn't there yet. Flip to false only for the very first run on a
    # machine that's never downloaded this model before (so it can fetch
    # it), or if you intentionally want to pick up model updates.
    SENTENCE_TRANSFORMER_LOCAL_FILES_ONLY: bool = True

    # Re-ranker: "cross_encoder" (default, local sentence-transformers model,
    # no external service) | "cohere" (hosted Rerank API, needs COHERE_API_KEY).
    RERANKER_PROVIDER: str = "cross_encoder"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # Same reasoning as SENTENCE_TRANSFORMER_LOCAL_FILES_ONLY above.
    RERANKER_LOCAL_FILES_ONLY: bool = True
    COHERE_API_KEY: str | None = None
    COHERE_RERANK_MODEL: str = "rerank-v3.5"

    # Web search tool (Phase 12): gives the chat model a web_search tool
    # alongside RAG document context, for questions the user's own documents
    # don't cover — current events, general external facts, etc. The model
    # decides per-turn whether to call it (only implemented for
    # LLM_PROVIDER=openai — see ollama_provider.py). Degrades to "no tool
    # offered" rather than failing chat if unconfigured — see
    # providers/websearch/factory.py.
    WEB_SEARCH_ENABLED: bool = True
    WEB_SEARCH_PROVIDER: str = "tavily"
    WEB_SEARCH_MAX_RESULTS: int = 5
    TAVILY_API_KEY: str | None = None
    TAVILY_SEARCH_DEPTH: str = "basic"  # "basic" | "advanced" (Tavily's own tiers)

    # Max tool-calling rounds per chat turn before the model is forced to
    # answer with tools=None — bounds the agent loop in chat_service.stream_reply
    # so a model that keeps requesting searches can't loop forever.
    CHAT_MAX_TOOL_HOPS: int = 3

    # Citation grounding: after the answer is fully streamed, one extra
    # non-streaming forced-tool-call asks the model which of the turn's
    # sources it actually used, and citations are filtered down to just
    # those — instead of always returning every source that was merely
    # retrieved/searched, whether the answer drew on it or not. Adds one
    # small LLM round-trip per turn; set false to skip it and keep the old
    # "return everything retrieved" behavior (also the automatic fallback
    # if the provider doesn't support forced tool calls, e.g. Ollama).
    CHAT_GROUNDING_ENABLED: bool = True

    # Chat (Phase 5): retrieval candidate/top-k for the RAG context, and how
    # many recent messages the short-term (Redis) buffer keeps per session.
    CHAT_RETRIEVAL_TOP_K: int = 5
    CHAT_RETRIEVAL_CANDIDATE_LIMIT: int = 20
    CHAT_RETRIEVAL_ALPHA: float = 0.5
    SHORT_TERM_MEMORY_TURNS: int = 10

    # Long-term memory backend (Phase 6): "sqlite" needs no extra service and
    # is the default; "weaviate" stores/searches summaries as a second
    # Weaviate collection (needs a plan that allows >1 collection).
    MEMORY_BACKEND: str = "sqlite"

    # Rate limiting (Phase 7), per client IP. "memory://" only works for a
    # single process — point at redis:// once running multiple workers.
    RATE_LIMIT_STORAGE_URI: str = "memory://"
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_CHAT: str = "20/minute"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
