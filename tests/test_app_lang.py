"""Regressão: idioma global controlado só pelo admin."""

from types import SimpleNamespace

from app.dependencies import get_app_lang, get_lang, set_lang_cookie
from app.models import Configuracao


def test_get_app_lang_defaults_to_pt():
    assert get_app_lang(None) == "pt"


def test_get_app_lang_from_app_state():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(app_lang="en", footer_config={})))
    assert get_app_lang(request) == "en"
    assert get_lang(request) == "en"


def test_get_app_lang_ignores_invalid():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(app_lang="fr", footer_config={"idioma": "es"})))
    assert get_app_lang(request) == "es"


def test_set_lang_cookie_is_noop():
    response = SimpleNamespace(cookies={})
    out = set_lang_cookie(response, "en")
    assert out is response


def test_configuracao_idioma_in_to_dict():
    cfg = Configuracao(id=1, idioma="en")
    data = cfg.to_dict()
    assert data["idioma"] == "en"
