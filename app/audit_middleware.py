"""
Middleware ASGI: audita POST/PUT/PATCH/DELETE bem-sucedidos (best-effort).
"""
from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.audit import should_auto_audit, summarize_http, write_audit


class AuditMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        if not should_auto_audit(method, path):
            await self.app(scope, receive, send)
            return

        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 500))
            await send(message)

        await self.app(scope, receive, send_wrapper)

        if status_code >= 400:
            return

        session = scope.get("session") or {}
        user = session.get("user") or {}
        # Login ainda não tem sessão no scope até o SessionMiddleware gravar —
        # para POST /login com sucesso, actor pode vir vazio; ok.
        state = scope.get("state") or {}
        request_id = state.get("request_id")
        client = scope.get("client")
        ip = client[0] if client else None
        action, entity_type, entity_id, summary = summarize_http(method, path, status_code)
        write_audit(
            actor_user_id=user.get("id"),
            actor_username=user.get("username"),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            ip=ip,
            request_id=request_id,
        )
