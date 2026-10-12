from datetime import date

from fastapi import Request, HTTPException
from fastapi.responses import Response


def get_current_user(request: Request) -> dict | None:
    return request.session.get("user")


# ──────────────────────────────────────────────────────────────
# Helpers de verificação de papel
# ──────────────────────────────────────────────────────────────

def is_admin(user: dict | None) -> bool:
    return bool(user and user.get("role") == "admin")


def is_maestro(user: dict | None) -> bool:
    return bool(user and user.get("role") in {"admin", "maestro"})


def is_arquivista(user: dict | None) -> bool:
    return bool(user and user.get("role") in {"admin", "arquivista"})


def is_secretaria(user: dict | None) -> bool:
    return bool(user and user.get("role") in {"admin", "secretaria"})


def can_manage_members(user: dict | None) -> bool:
    """Maestro e secretaria podem adicionar/editar membros; admin pode tudo."""
    return bool(user and user.get("role") in {"admin", "maestro", "secretaria"})


def can_manage_patrimonio(user: dict | None) -> bool:
    """Arquivista pode criar/editar/vincular patrimônio; admin pode tudo."""
    return bool(user and user.get("role") in {"admin", "arquivista"})


def can_manage_acervo(user: dict | None) -> bool:
    """Maestro e arquivista podem gerenciar o acervo musical; admin pode tudo."""
    return bool(user and user.get("role") in {"admin", "maestro", "arquivista"})


# ──────────────────────────────────────────────────────────────
# Dependências FastAPI (usadas em Depends())
# ──────────────────────────────────────────────────────────────

def require_admin(request: Request) -> dict:
    """Restringe a administradores. Levanta 403 caso contrário."""
    user = get_current_user(request)
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
    return user


def require_manage_members(request: Request) -> dict:
    """Permite admin, maestro e secretaria. Levanta 403 para user/arquivista."""
    user = get_current_user(request)
    if not can_manage_members(user):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores, maestros e secretaria.")
    return user


def require_manage_patrimonio(request: Request) -> dict:
    """Permite admin e arquivista. Levanta 403 para demais papéis."""
    user = get_current_user(request)
    if not can_manage_patrimonio(user):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores e arquivistas.")
    return user


def require_manage_acervo(request: Request) -> dict:
    """Permite admin, maestro e arquivista. Levanta 403 para demais papéis."""
    user = get_current_user(request)
    if not can_manage_acervo(user):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores, maestros e arquivistas.")
    return user


# ──────────────────────────────────────────────────────────────
# Internacionalização e contexto de template
# ──────────────────────────────────────────────────────────────

def get_app_lang(request: Request | None = None) -> str:
    """Idioma global da aplicação (definido pelo admin)."""
    if request is not None:
        lang = getattr(request.app.state, "app_lang", None)
        if lang in {"pt", "en", "es"}:
            return lang
        footer = getattr(request.app.state, "footer_config", {}) or {}
        lang = footer.get("idioma")
        if lang in {"pt", "en", "es"}:
            return lang
    return "pt"


def get_lang(request: Request) -> str:
    """Compat: retorna o idioma global (usuários não escolhem idioma)."""
    return get_app_lang(request)


def make_ctx(request: Request, extra: dict = None) -> dict:
    """Build a template context dict with lang, translations, current_user and branding."""
    lang = get_app_lang(request)
    translations = getattr(request.app.state, "translations", {}) or {}
    t = translations.get(lang) or translations.get("pt") or {}
    branding = getattr(request.app.state, "branding", {})
    user = get_current_user(request)
    ctx = {
        "request":              request,
        "t":                    t,
        "lang":                 lang,
        "now":                  date.today().isoformat(),
        "current_user":         user,
        "brand_logo":           branding.get("logo"),
        "footer_config":        getattr(request.app.state, "footer_config", {}),
        "app_version":          getattr(request.app.state, "app_version", "1.0.0"),
        # flags de permissão prontos para uso nos templates
        "can_manage_members":   can_manage_members(user),
        "can_manage_patrimonio": can_manage_patrimonio(user),
        "can_manage_acervo":    can_manage_acervo(user),
        "is_admin":             is_admin(user),
    }
    if extra:
        ctx.update(extra)
    return ctx


def set_lang_cookie(response: Response, lang: str) -> Response:
    """Mantido por compatibilidade com handlers existentes (no-op útil)."""
    # Idioma é global; cookie não controla mais a UI.
    return response
