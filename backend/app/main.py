# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# FastAPI application factory. Only wires middleware and routers together —
# no business logic lives here.

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.routers.audit_log_router import router as audit_log_router
from app.api.v1.routers.auth_router import router as auth_router
from app.api.v1.routers.chat_router import router as chat_router
from app.api.v1.routers.departments_router import router as departments_router
from app.api.v1.routers.documents_router import router as documents_router
from app.api.v1.routers.health_router import router as health_router
from app.api.v1.routers.retrieval_router import router as retrieval_router
from app.api.v1.routers.users_router import router as users_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.observability_middleware import ObservabilityMiddleware
from app.core.rate_limit import limiter
from app.providers.embeddings.factory import get_embedding_provider
from app.providers.reranker.factory import get_reranker

logger = logging.getLogger(__name__)


def _rate_limit_exceeded_handler(request, exc: RateLimitExceeded) -> Response:
    return Response(
        content=f'{{"detail": "Rate limit exceeded: {exc.detail}"}}',
        status_code=429,
        media_type="application/json",
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # get_embedding_provider/get_reranker are @lru_cache'd, so whichever
    # request happened to be first to need one used to pay for loading it
    # (and, for the local sentence-transformers-backed providers, the
    # one-time HF metadata chatter) mid-request. Loading both here means
    # that cost is paid once at boot instead, off the request path.
    start = time.monotonic()
    get_embedding_provider()
    get_reranker()
    logger.info("Warmed embedding provider and reranker in %.3fs", time.monotonic() - start)
    yield


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=_lifespan)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(ObservabilityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Response headers are invisible to browser JS across origins unless
        # explicitly exposed here — browsers only auto-expose a small
        # CORS-safelisted set (Content-Type, Content-Length, ...), which
        # neither of these is. Without this, the frontend's X-Total-Count
        # read (pagination) and Content-Disposition read (download filename)
        # both silently fail: curl sees the headers fine (no CORS there),
        # which is what made this easy to miss.
        expose_headers=["X-Total-Count", "Content-Disposition"],
    )

    app.include_router(health_router, prefix=settings.API_V1_PREFIX)
    app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
    app.include_router(users_router, prefix=settings.API_V1_PREFIX)
    app.include_router(departments_router, prefix=settings.API_V1_PREFIX)
    app.include_router(documents_router, prefix=settings.API_V1_PREFIX)
    app.include_router(retrieval_router, prefix=settings.API_V1_PREFIX)
    app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
    app.include_router(audit_log_router, prefix=settings.API_V1_PREFIX)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        # Unauthenticated on purpose, matching standard Prometheus exporter
        # convention — restrict access at the network layer (firewall/
        # reverse proxy), not app-level auth, when deploying for real.
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
