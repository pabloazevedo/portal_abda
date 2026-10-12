"""Regressão do hub de Configurações."""
from types import SimpleNamespace

from starlette.requests import Request
from starlette.datastructures import Headers

from app.routers.settings import (
    VALID_SECTIONS,
    _resolve_section,
    _resolve_flash,
    _settings_redirect,
    _smtp_safe,
)


def _req(query: str = ""):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/settings/",
        "raw_path": b"/settings/",
        "query_string": query.encode(),
        "headers": Headers({}).raw,
        "client": ("127.0.0.1", 1),
        "server": ("test", 80),
        "app": SimpleNamespace(state=SimpleNamespace()),
        "session": {},
        "state": {},
    }
    return Request(scope)


def test_valid_sections():
    assert VALID_SECTIONS == {"geral", "aparencia", "email", "dados", "sistema"}


def test_resolve_section_default():
    assert _resolve_section(_req()) == "geral"


def test_resolve_section_explicit():
    assert _resolve_section(_req("section=email")) == "email"
    assert _resolve_section(_req("section=nope")) == "geral"


def test_resolve_section_legacy_aliases():
    assert _resolve_section(_req("smtp_saved=1")) == "email"
    assert _resolve_section(_req("success=1")) == "aparencia"
    assert _resolve_section(_req("idioma_saved=1")) == "geral"
    assert _resolve_section(_req("open=idioma")) == "geral"
    assert _resolve_section(_req("ok=smtp_test_ok")) == "email"


def test_resolve_flash_ok_and_legacy():
    f = _resolve_flash(_req("ok=geral_saved"))
    assert f and f["variant"] == "success"
    f2 = _resolve_flash(_req("smtp_saved=1"))
    assert f2 and "e-mail" in f2["message"].lower() or "email" in f2["message"].lower() or "E-mail" in f2["message"] or "Configurações" in f2["message"]


def test_settings_redirect():
    r = _settings_redirect("email", "smtp_saved")
    assert r.status_code == 303
    assert r.headers["location"] == "/settings/?section=email&ok=smtp_saved"


def test_smtp_safe_hides_password():
    safe = _smtp_safe({"smtp_host": "h", "smtp_password": "secret", "app_base_url": "https://x"})
    assert "smtp_password" not in safe
    assert safe["password_set"] is True
    assert safe["app_base_url"] == "https://x"
