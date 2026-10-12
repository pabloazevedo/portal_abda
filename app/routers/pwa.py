"""Site mobile / PWA em /m — shell HTML + API Bearer (/api/v1)."""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates

from app.dependencies import get_lang, make_ctx
from app.pdf_tickets import consume_pdf_ticket

router = APIRouter(prefix="/m", tags=["PWA"])
templates = Jinja2Templates(directory="templates")

STATIC_PWA = Path("static/pwa")
SW_PATH = STATIC_PWA / "sw.js"


def _pwa_enabled(request: Request) -> bool:
    fc = getattr(request.app.state, "footer_config", None) or {}
    return bool(fc.get("pwa_enabled"))


def _brand_name(request: Request) -> str:
    fc = getattr(request.app.state, "footer_config", None) or {}
    name = (fc.get("nome_institucional") or "").strip()
    return name or "Portal"


def _disabled_response(request: Request):
    return templates.TemplateResponse(
        "pwa/disabled.html",
        make_ctx(
            request,
            {
                "brand_name": _brand_name(request),
                "pwa_enabled": False,
            },
        ),
        status_code=503,
    )


@router.get("/", response_class=HTMLResponse)
@router.get("", response_class=HTMLResponse)
async def pwa_home(request: Request):
    if not _pwa_enabled(request):
        return _disabled_response(request)
    return templates.TemplateResponse(
        "pwa/app.html",
        make_ctx(
            request,
            {
                "brand_name": _brand_name(request),
                "pwa_enabled": True,
                "page": "app",
            },
        ),
    )


@router.get("/login", response_class=HTMLResponse)
async def pwa_login(request: Request):
    if not _pwa_enabled(request):
        return _disabled_response(request)
    return templates.TemplateResponse(
        "pwa/login.html",
        make_ctx(
            request,
            {
                "brand_name": _brand_name(request),
                "pwa_enabled": True,
                "page": "login",
            },
        ),
    )


@router.get("/pdf/{ticket}")
async def pwa_pdf_ticket(ticket: str, request: Request):
    """Serve PDF inline via ticket (viewer nativo no smartphone)."""
    if not _pwa_enabled(request):
        raise HTTPException(status_code=503, detail="PWA desligado.")
    row = consume_pdf_ticket(ticket, redis_client=getattr(request.app.state, "redis", None))
    if not row:
        raise HTTPException(status_code=410, detail="Link de visualização expirado. Abra novamente no app.")
    path = Path(row.path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    fname = row.filename or "partitura.pdf"
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=fname,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{fname}"',
        },
    )


@router.get("/manifest.webmanifest")
async def pwa_manifest(request: Request):
    if not _pwa_enabled(request):
        return JSONResponse({"detail": "PWA desligado."}, status_code=404)
    name = _brand_name(request)
    short = name if len(name) <= 12 else "Portal"
    body = {
        "name": f"{name} — Partituras",
        "short_name": short,
        "description": "Partituras do músico",
        "start_url": "/m/",
        "scope": "/m/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#0f2744",
        "theme_color": "#1A365C",
        "lang": get_lang(request),
        "icons": [
            {
                "src": "/static/pwa/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/static/pwa/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/static/pwa/icons/icon-512-maskable.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return Response(
        content=json.dumps(body, ensure_ascii=False),
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/sw.js")
async def pwa_service_worker(request: Request):
    if not _pwa_enabled(request):
        return PlainTextResponse("// PWA disabled", status_code=404)
    if not SW_PATH.is_file():
        return PlainTextResponse("// missing sw", status_code=404)
    content = SW_PATH.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="application/javascript; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Service-Worker-Allowed": "/m/",
        },
    )
