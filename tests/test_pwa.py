"""Testes do site mobile / PWA (/m) e flag em Configurações."""
import pytest
from fastapi.testclient import TestClient

pytest.importorskip("httpx")

from app.main import app
from app.database import SessionLocal
from app.models import Configuracao


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def _set_pwa(db, enabled: bool):
    cfg = db.query(Configuracao).filter(Configuracao.id == 1).first()
    if cfg is None:
        cfg = Configuracao(id=1, pwa_enabled=enabled)
        db.add(cfg)
    else:
        cfg.pwa_enabled = enabled
    db.commit()
    db.refresh(cfg)
    return cfg


def test_pwa_disabled_returns_503(client, db):
    _set_pwa(db, False)
    # sync app.state used by routes
    client.app.state.footer_config = {**(getattr(client.app.state, "footer_config", None) or {}), "pwa_enabled": False}
    r = client.get("/m/")
    assert r.status_code == 503
    assert "desligado" in r.text.lower() or "desactiv" in r.text.lower() or "off" in r.text.lower()
    assert client.get("/m/manifest.webmanifest").status_code == 404
    assert client.get("/m/sw.js").status_code == 404


def test_pwa_enabled_serves_shell(client, db):
    _set_pwa(db, True)
    client.app.state.footer_config = {**(getattr(client.app.state, "footer_config", None) or {}), "pwa_enabled": True}
    r = client.get("/m/")
    assert r.status_code == 200
    assert "/static/pwa/app.js" in r.text
    login = client.get("/m/login")
    assert login.status_code == 200
    man = client.get("/m/manifest.webmanifest")
    assert man.status_code == 200
    assert man.json()["start_url"] == "/m/"
    sw = client.get("/m/sw.js")
    assert sw.status_code == 200
    assert "portal-pwa-shell" in sw.text


def test_pwa_does_not_break_musicians_auth_gate(client):
    # /musicians must NOT be treated as public /m
    r = client.get("/musicians/", follow_redirects=False)
    assert r.status_code in (302, 303, 307, 401, 403)
    loc = (r.headers.get("location") or "").lower()
    if r.status_code in (302, 303, 307):
        assert "/login" in loc


def test_pwa_app_includes_notices_region(client, db):
    _set_pwa(db, True)
    client.app.state.footer_config = {
        **(getattr(client.app.state, "footer_config", None) or {}),
        "pwa_enabled": True,
    }
    r = client.get("/m/")
    assert r.status_code == 200
    assert 'id="pwa-notices"' in r.text
    assert "pwa-notices-clear" in r.text


def test_resolve_pwa_flash_section():
    from tests.test_settings_hub import _req
    from app.routers.settings import _resolve_section, _resolve_flash

    assert _resolve_section(_req("ok=pwa_saved")) == "sistema"
    f = _resolve_flash(_req("ok=pwa_saved"))
    assert f and f["variant"] == "success"
