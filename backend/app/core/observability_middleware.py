# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Request-ID + Prometheus request metrics, as one raw ASGI middleware —
# deliberately NOT Starlette's BaseHTTPMiddleware, which is documented to
# (a) run the downstream app in a separate task, breaking the request_id
# contextvar's propagation into route handlers, and (b) buffer streaming
# responses, which would break the chat SSE endpoint. A plain ASGI
# middleware runs in the same task and passes `send` messages through
# untouched, avoiding both problems.

import time
import uuid
from collections.abc import Awaitable, Callable

from prometheus_client import Counter, Histogram
from starlette.datastructures import MutableHeaders
from starlette.types import Message, Receive, Scope, Send

from app.core.logging import request_id_var

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "path"]
)


class ObservabilityMiddleware:
    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = (
            next(
                (v.decode() for k, v in scope.get("headers", []) if k == b"x-request-id"),
                None,
            )
            or uuid.uuid4().hex
        )
        token = request_id_var.set(request_id)

        status_code = 500
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message).append("X-Request-ID", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_var.reset(token)
            duration = time.perf_counter() - start
            route = scope.get("route")
            path_template = route.path if route is not None else scope.get("path", "unknown")
            method = scope.get("method", "-")
            REQUEST_COUNT.labels(method=method, path=path_template, status=status_code).inc()
            REQUEST_DURATION.labels(method=method, path=path_template).observe(duration)
