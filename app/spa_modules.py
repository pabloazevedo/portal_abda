"""
Hybrid SPA: quais prefixos do desktop são servidos pela React SPA.

SPA_MODULES=home,users,musicians,...
SPA_MODULES=*  → todos os módulos (exceto rotas públicas reservadas)
SPA_DESKTOP=1  → alias de *

Jinja permanece montado; SpaModulesMiddleware serve o index só nos paths allowlisted.
"""
from __future__ import annotations

import os
from pathlib import Path

SPA_DIR = Path("frontend/dist")

MODULE_PREFIXES: dict[str, tuple[str, ...]] = {
    "auth": ("/login", "/forgot-password", "/reset-password"),
    "home": ("/",),
    "search": ("/search",),
    "users": ("/users",),
    "musicians": ("/musicians",),
    "patrimonio": ("/patrimonio",),
    "acervo": ("/acervo",),
    "programacao": ("/acervo/programacao",),
    "settings": ("/settings",),
    "releases": ("/releases", "/versoes"),
}

ALL_MODULES = frozenset(MODULE_PREFIXES.keys())


def spa_dist_ready() -> bool:
    return SPA_DIR.is_dir() and (SPA_DIR / "index.html").is_file()


def parse_spa_modules() -> frozenset[str]:
    raw = (os.getenv("SPA_MODULES") or "").strip()
    if not raw:
        if os.getenv("SPA_DESKTOP", "0") == "1":
            return ALL_MODULES
        return frozenset()
    if raw in {"*", "all", "ALL"}:
        return ALL_MODULES
    parts = {p.strip().lower() for p in raw.split(",") if p.strip()}
    return frozenset(parts & ALL_MODULES)


def _is_public_reserved(path: str) -> bool:
    """Rotas que nunca vão para a SPA (API, PWA, públicos, assets)."""
    if path in {"/healthz", "/readyz"}:
        return True
    reserved = (
        "/api",
        "/m/",
        "/uploads/",
        "/static/",
        "/assets/",
        "/favicon",
        "/instrumentos",
        "/patrimonio/qr",
        "/patrimonio/scan",
        "/acervo/programacao/acesso",
        "/acervo/programacao/ical",
        "/acervo/calendario.ics",
    )
    if path == "/m":
        return True
    for p in reserved:
        if path == p.rstrip("/") or path.startswith(p):
            return True
    return False


def path_served_by_spa(path: str, modules: frozenset[str] | None = None) -> bool:
    if not spa_dist_ready():
        return False
    mods = modules if modules is not None else parse_spa_modules()
    if not mods:
        return False
    if _is_public_reserved(path):
        return False

    # programacao antes de acervo (mais específico)
    if "programacao" in mods:
        if path == "/acervo/programacao" or path.startswith("/acervo/programacao/"):
            return True

    for mod in mods:
        for prefix in MODULE_PREFIXES.get(mod, ()):
            if prefix == "/":
                if path == "/":
                    return True
                continue
            if path == prefix or path.startswith(prefix + "/"):
                if mod == "acervo" and (
                    path == "/acervo/programacao" or path.startswith("/acervo/programacao/")
                ):
                    return "programacao" in mods
                if mod == "patrimonio" and (
                    path.startswith("/patrimonio/qr") or path.startswith("/patrimonio/scan")
                ):
                    return False
                return True
    return False
