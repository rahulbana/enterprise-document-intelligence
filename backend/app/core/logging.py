# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Process-wide logging configuration. Every record carries a request_id
# (from RequestIdMiddleware's contextvar, "-" outside a request) so log
# lines from the same HTTP request can be correlated — in either format.
# LOG_FORMAT=json emits one JSON object per line for log aggregators;
# "text" (default) stays human-readable for local dev.
#
# Structured fields: a caller can pass logging.info(msg, extra={...}) to
# attach queryable fields (e.g. chat_service's per-turn tool-selection
# telemetry) beyond the fixed timestamp/level/logger/message ones below —
# _EXTRA_FIELD_BLOCKLIST is every attribute a plain LogRecord already has,
# so only what a caller actually passed via extra= gets treated as "extra".

import json
import logging
from contextvars import ContextVar

from app.core.config import settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_EXTRA_FIELD_BLOCKLIST = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "request_id",
}


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def _extra_fields(record: logging.LogRecord) -> dict:
    return {k: v for k, v in record.__dict__.items() if k not in _EXTRA_FIELD_BLOCKLIST}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        payload.update(_extra_fields(record))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extra = _extra_fields(record)
        if not extra:
            return base
        return base + " | " + " ".join(f"{k}={v!r}" for k, v in extra.items())


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    if settings.LOG_FORMAT == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            _TextFormatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | [%(request_id)s] | %(message)s"
            )
        )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    root.handlers = [handler]
