# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Celery application. Redis doubles as broker and result backend (also used
# directly, not through Celery, for short-term chat memory — see
# app/memory/short_term.py).
# Start a worker with: celery -A app.workers.celery_app worker --loglevel=info

import logging
import time

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "document_intelligence",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.ingestion_tasks", "app.workers.memory_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_max_tasks_per_child=100,
)


@worker_process_init.connect
def _warm_embedding_provider(**_kwargs) -> None:
    # Without this, whichever ingestion task happened to run first in a
    # given worker process paid for loading the embedding model (and, for
    # the local sentence-transformers provider, the one-time HF metadata
    # chatter) — same fix as app.main's startup hook, applied to the worker
    # side of the app instead of the API side.
    from app.providers.embeddings.factory import get_embedding_provider

    start = time.monotonic()
    get_embedding_provider()
    logger.info("Warmed embedding provider in %.3fs", time.monotonic() - start)
