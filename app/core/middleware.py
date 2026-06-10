import time
from uuid import uuid4

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = structlog.get_logger()


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request_id = uuid4().hex[:12]
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            log.info(
                "request",
                request_id=request_id,
                method=scope.get("method") or scope["type"],
                path=scope.get("path", ""),
                status=status_holder["status"],
                latency_ms=latency_ms,
            )
            structlog.contextvars.unbind_contextvars("request_id")
