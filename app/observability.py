"""
Observabilidade mínima (P0): request ID + log de acesso.
Middleware ASGI puro — não bufferiza o body (uploads seguros).
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("uvicorn.error")

SKIP_ACCESS_LOG_PREFIXES = ("/static", "/uploads", "/favicon")


class RequestContextMiddleware:
    """Injeta X-Request-ID e registra uma linha de access log por request HTTP."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        request_id = (headers.get("x-request-id") or "").strip() or uuid.uuid4().hex[:16]
        scope.setdefault("state", {})
        # Starlette Request.state is populated from scope["state"] by the framework
        if "state" not in scope:
            scope["state"] = {}

        # Guarda no scope para Request.state.request_id
        scope["state"]["request_id"] = request_id

        path = scope.get("path", "")
        method = scope.get("method", "")
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
                raw_headers = list(message.get("headers") or [])
                raw_headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": raw_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if not any(path.startswith(p) for p in SKIP_ACCESS_LOG_PREFIXES):
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "access method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
                    method,
                    path,
                    status_code,
                    elapsed_ms,
                    request_id,
                )


def get_request_id(request) -> str:
    return getattr(request.state, "request_id", None) or "-"
