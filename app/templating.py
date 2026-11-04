"""Templates Jinja com a assinatura antiga de TemplateResponse.

O Starlette 1.x passou a exigir TemplateResponse(request, nome, contexto).
O restante do portal ainda chama TemplateResponse(nome, contexto).
"""
from typing import Any, Mapping

from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask
from starlette.requests import Request


class Templates(Jinja2Templates):
    def TemplateResponse(
        self,
        name: str,
        context: dict[str, Any] | None = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ):
        context = context or {}
        request = context.get("request")
        if not isinstance(request, Request):
            raise RuntimeError("O contexto do template precisa incluir request.")
        return super().TemplateResponse(
            request,
            name,
            context,
            status_code,
            headers,
            media_type,
            background,
        )
