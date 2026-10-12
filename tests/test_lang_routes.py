"""Smoke autenticado: idioma só admin; CTAs e chrome sem seletor de idioma."""
from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.datastructures import Headers

from app.main import set_lang
from app.dependencies import get_app_lang, make_ctx


def _request(path="/", user=None, app_lang="pt"):
    app = SimpleNamespace(
        state=SimpleNamespace(
            app_lang=app_lang,
            footer_config={"idioma": app_lang},
            translations={"pt": {"app_title": "Portal"}, "en": {"app_title": "Portal"}, "es": {"app_title": "Portal"}},
            branding={},
            app_version="test",
        )
    )
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": Headers({}).raw,
        "client": ("127.0.0.1", 123),
        "server": ("testserver", 80),
        "app": app,
        "session": {"user": user} if user else {},
        "state": {},
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_set_lang_admin_goes_to_settings():
    req = _request(user={"id": 1, "username": "admin", "role": "admin"})
    resp = await set_lang("en", req)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/settings/?section=geral"


@pytest.mark.asyncio
async def test_set_lang_user_goes_home():
    req = _request(user={"id": 2, "username": "u", "role": "user"})
    resp = await set_lang("en", req)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


@pytest.mark.asyncio
async def test_set_lang_anon_goes_home():
    req = _request(user=None)
    resp = await set_lang("es", req)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_make_ctx_uses_global_lang():
    req = _request(app_lang="es", user={"id": 1, "role": "user"})
    ctx = make_ctx(req)
    assert ctx["lang"] == "es"
    assert get_app_lang(req) == "es"
    assert ctx["can_manage_members"] is False
    assert ctx["is_admin"] is False
