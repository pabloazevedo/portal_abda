"""
Portal — Router de Configurações / Branding / Exportação.
"""

import base64
import csv
import hashlib
import io
import json
import logging
import os
import uuid
from datetime import datetime, date
from sqlalchemy import extract
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from cryptography.fernet import Fernet, InvalidToken

from fastapi import APIRouter, Depends, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from app.templating import Templates
from sqlalchemy.orm import Session

from fastapi import Form

from app.database import get_db
from app.labels import TIPO_LABEL as _PATRIMONIO_TIPO_LABEL, STATUS_LABEL as _PATRIMONIO_STATUS_LABEL  # D-01
from app.models import Musician, User, Patrimonio, TipoItem, StatusPatrimonio, Configuracao
from app.dependencies import make_ctx, set_lang_cookie, require_admin, get_lang
from app.email_utils import send_test_email
from app.utils import detect_image_type  # D-02

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/settings")
templates = Templates(directory="templates")

# ── Redis helpers para cache do rodapé ───────────────────────
_FOOTER_CACHE_KEY = "footer_config"
_FOOTER_CACHE_TTL = 3600  # 1 hora


def _redis(request: Request):
    return getattr(request.app.state, "redis", None)


def _cache_get_footer(r) -> dict | None:
    if r is None:
        return None
    try:
        raw = r.get(_FOOTER_CACHE_KEY)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_set_footer(r, data: dict) -> None:
    if r is None:
        return
    try:
        r.setex(_FOOTER_CACHE_KEY, _FOOTER_CACHE_TTL, json.dumps(data, ensure_ascii=False))
    except Exception:
        pass


def _cache_del_footer(r) -> None:
    if r is None:
        return
    try:
        r.delete(_FOOTER_CACHE_KEY)
    except Exception:
        pass


def _get_footer_config(request: Request, db: Session) -> dict:
    """Lê config do rodapé: Redis → BD → cria padrão."""
    r = _redis(request)
    cached = _cache_get_footer(r)
    if cached is not None:
        return cached

    cfg = db.query(Configuracao).filter(Configuracao.id == 1).first()
    if cfg is None:
        cfg = Configuracao(id=1)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)

    data = cfg.to_dict()
    _cache_set_footer(r, data)
    return data

UPLOAD_DIR = Path("uploads")
MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2 MB
ALLOWED_LOGO_EXT = {".png", ".jpg", ".jpeg", ".svg", ".webp"}

# S-03: chave Fernet derivada da SECRET_KEY para cifrar a senha SMTP no JSON
_SK = os.getenv("SECRET_KEY", "change-me-in-production-use-32-random-chars")
_FERNET: Fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(_SK.encode()).digest()))


def _is_svg(data: bytes) -> bool:
    try:
        head = data[:512].decode("utf-8", errors="ignore").lstrip()
        return head.startswith("<svg") or "<?xml" in head[:50]
    except Exception:
        return False


def _validate_logo(data: bytes, ext: str) -> bool:
    if ext == ".svg":
        return _is_svg(data)
    detected = detect_image_type(data)  # D-02: usa utilitário centralizado
    if detected is None:
        return False
    if ext in {".jpg", ".jpeg"} and detected == ".jpg":
        return True
    return detected == ext


def _branding_file() -> Path:
    return UPLOAD_DIR / "branding.json"


def _read_branding() -> dict:
    f = _branding_file()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write_branding(data: dict):
    _branding_file().write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ── SMTP settings helpers ─────────────────────────────────────

def _smtp_file() -> Path:
    return UPLOAD_DIR / "app_settings.json"


def _encrypt_password(plain: str) -> str:
    """S-03: cifra a senha SMTP antes de gravar no JSON."""
    return _FERNET.encrypt(plain.encode("utf-8")).decode("utf-8")


def _decrypt_password(token: str) -> str:
    """S-03: decifra a senha SMTP lida do JSON; aceita texto plano legado como fallback."""
    try:
        return _FERNET.decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        return token  # fallback para configs gravadas antes da criptografia


def _read_smtp() -> dict:
    f = _smtp_file()
    if f.exists():
        try:
            cfg = json.loads(f.read_text(encoding="utf-8"))
            if cfg.get("smtp_password"):
                cfg["smtp_password"] = _decrypt_password(cfg["smtp_password"])
            return cfg
        except Exception:
            pass
    return {}


def _write_smtp(data: dict):
    to_save = dict(data)
    if to_save.get("smtp_password"):
        to_save["smtp_password"] = _encrypt_password(to_save["smtp_password"])
    _smtp_file().write_text(json.dumps(to_save, ensure_ascii=False), encoding="utf-8")


def _smtp_safe(cfg: dict) -> dict:
    """Retorna cópia sem a senha real — só indica se está configurada."""
    return {
        "smtp_host":     cfg.get("smtp_host", ""),
        "smtp_port":     cfg.get("smtp_port", 587),
        "smtp_user":     cfg.get("smtp_user", ""),
        "smtp_from":     cfg.get("smtp_from", ""),
        "smtp_tls":      cfg.get("smtp_tls", True),
        "app_base_url":  cfg.get("app_base_url", ""),
        "password_set":  bool(cfg.get("smtp_password")),
    }


VALID_SECTIONS = {"geral", "aparencia", "email", "dados", "sistema"}

_FLASH_MESSAGES = {
    "logo_saved":     ("Logo atualizado com sucesso.", "success"),
    "logo_removed":   ("Logo removido. Será exibido o ícone padrão.", "success"),
    "smtp_saved":     ("Configurações de e-mail salvas.", "success"),
    "smtp_test_ok":   ("E-mail de teste enviado com sucesso.", "success"),
    "smtp_test_fail": ("Falha no envio do e-mail de teste.", "danger"),
    "footer_saved":   ("Dados do rodapé salvos com sucesso.", "success"),
    "idioma_saved":   ("Idioma da aplicação atualizado.", "success"),
    "geral_saved":    ("Configurações gerais salvas.", "success"),
    "retention_saved": ("Retenção de auditoria atualizada.", "success"),
    "pwa_saved":      ("Site mobile / PWA atualizado.", "success"),
}


def _resolve_section(request: Request) -> str:
    qs = request.query_params
    explicit = (qs.get("section") or "").strip().lower()
    if explicit in VALID_SECTIONS:
        return explicit
    if qs.get("open") == "idioma" or qs.get("idioma_saved") or qs.get("geral_saved") or qs.get("ok") in {"idioma_saved", "geral_saved"}:
        return "geral"
    if qs.get("smtp_saved") or qs.get("smtp_test") or qs.get("ok") in {"smtp_saved", "smtp_test_ok", "smtp_test_fail"}:
        return "email"
    if qs.get("success") or qs.get("removed") or qs.get("footer_saved") or qs.get("ok") in {"logo_saved", "logo_removed", "footer_saved"}:
        return "aparencia"
    if qs.get("ok") == "retention_saved" or qs.get("ok") == "pwa_saved":
        return "sistema"
    return "geral"


def _resolve_flash(request: Request) -> dict | None:
    qs = request.query_params
    ok = qs.get("ok")
    if ok and ok in _FLASH_MESSAGES:
        msg, variant = _FLASH_MESSAGES[ok]
        if ok == "smtp_test_ok" and qs.get("to"):
            msg = f"E-mail de teste enviado para {qs.get('to')}."
        if ok == "smtp_test_fail" and qs.get("err"):
            msg = f"Falha no envio: {qs.get('err')}"
        return {"message": msg, "variant": variant}
    # Legado (query params antigos)
    if qs.get("success"):
        return {"message": _FLASH_MESSAGES["logo_saved"][0], "variant": "success"}
    if qs.get("removed"):
        return {"message": _FLASH_MESSAGES["logo_removed"][0], "variant": "success"}
    if qs.get("smtp_saved"):
        return {"message": _FLASH_MESSAGES["smtp_saved"][0], "variant": "success"}
    if qs.get("smtp_test") == "ok":
        to = qs.get("to") or ""
        return {"message": f"E-mail de teste enviado para {to}." if to else _FLASH_MESSAGES["smtp_test_ok"][0], "variant": "success"}
    if qs.get("smtp_test") == "fail":
        err = qs.get("err") or ""
        return {"message": f"Falha no envio: {err}" if err else _FLASH_MESSAGES["smtp_test_fail"][0], "variant": "danger"}
    if qs.get("footer_saved"):
        return {"message": _FLASH_MESSAGES["footer_saved"][0], "variant": "success"}
    if qs.get("idioma_saved"):
        return {"message": _FLASH_MESSAGES["idioma_saved"][0], "variant": "success"}
    return None


def _settings_redirect(section: str, ok: str | None = None, extra: str = "") -> RedirectResponse:
    sec = section if section in VALID_SECTIONS else "geral"
    url = f"/settings/?section={sec}"
    if ok:
        url += f"&ok={ok}"
    if extra:
        url += f"&{extra}" if not extra.startswith("&") else extra
    return RedirectResponse(url=url, status_code=303)


def _full_settings_ctx(request: Request, db: Session, extra: dict | None = None) -> dict:
    from app.audit import AUDIT_RETENTION_MIN, AUDIT_RETENTION_MAX, AUDIT_RETENTION_DEFAULT, clamp_retention_days

    flash = _resolve_flash(request)
    footer = _get_footer_config(request, db)
    retention = clamp_retention_days(footer.get("audit_retention_days", AUDIT_RETENTION_DEFAULT))
    data = {
        "branding":            _read_branding(),
        "smtp":                _smtp_safe(_read_smtp()),
        "footer_config":       footer,
        "settings_section":    _resolve_section(request),
        "settings_flash":      flash,
        "settings_flash_json": json.dumps(flash, ensure_ascii=False) if flash else "null",
        "mes_atual":           date.today().month,
        "audit_retention_days": retention,
        "audit_retention_min": AUDIT_RETENTION_MIN,
        "audit_retention_max": AUDIT_RETENTION_MAX,
        "pwa_enabled": bool(footer.get("pwa_enabled")),
    }
    if extra:
        data.update(extra)
        if "error" in extra and "settings_section" not in extra:
            data["settings_section"] = "aparencia"
    return make_ctx(request, data)


# ──────────────────────────────────────────────────────────────
# GET /settings/
# ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    ctx = _full_settings_ctx(request, db)
    resp = templates.TemplateResponse("settings/index.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


# ──────────────────────────────────────────────────────────────
# POST /settings/logo
# ──────────────────────────────────────────────────────────────

@router.post("/logo")
async def upload_logo(
    request: Request,
    db: Session = Depends(get_db),
    logo: UploadFile = File(...),
    _admin: dict = Depends(require_admin),
):
    lang = get_lang(request)
    ext = Path(logo.filename).suffix.lower() if logo.filename else ""

    def _err(msg: str):
        ctx = _full_settings_ctx(request, db, {"error": msg, "settings_section": "aparencia"})
        resp = templates.TemplateResponse("settings/index.html", ctx)
        return set_lang_cookie(resp, lang)

    if ext not in ALLOWED_LOGO_EXT:
        return _err(f"Formato não suportado: {ext or '(sem extensão)'}. Use PNG, JPG, SVG ou WebP.")

    data = await logo.read()

    if len(data) == 0:
        return _err("Arquivo vazio.")

    if len(data) > MAX_LOGO_SIZE:
        return _err("Arquivo muito grande. Limite: 2 MB.")

    if not _validate_logo(data, ext):
        return _err("Conteúdo do arquivo não corresponde ao formato declarado.")

    # Remove logo anterior
    branding = _read_branding()
    old_logo = branding.get("logo")
    if old_logo:
        old_path = UPLOAD_DIR / old_logo
        if old_path.exists():
            old_path.unlink()

    filename = f"logo_{uuid.uuid4()}{ext}"
    (UPLOAD_DIR / filename).write_bytes(data)

    branding["logo"] = filename
    _write_branding(branding)

    # Atualiza estado em memória para refletir imediatamente
    request.app.state.branding = branding

    logger.info(f"[Portal] Logo atualizado: {filename}")
    resp = _settings_redirect("aparencia", "logo_saved")
    return set_lang_cookie(resp, lang)


# ──────────────────────────────────────────────────────────────
# POST /settings/logo/remove
# ──────────────────────────────────────────────────────────────

@router.post("/logo/remove")
async def remove_logo(
    request: Request,
    _admin: dict = Depends(require_admin),
):
    lang = get_lang(request)
    branding = _read_branding()
    old_logo = branding.pop("logo", None)
    if old_logo:
        old_path = UPLOAD_DIR / old_logo
        if old_path.exists():
            old_path.unlink()
    _write_branding(branding)
    request.app.state.branding = branding

    logger.info("[Portal] Logo removido.")
    resp = _settings_redirect("aparencia", "logo_removed")
    return set_lang_cookie(resp, lang)


# ──────────────────────────────────────────────────────────────
# POST /settings/smtp — salvar configurações SMTP
# ──────────────────────────────────────────────────────────────

@router.post("/smtp")
async def save_smtp(
    request: Request,
    smtp_host:    str           = Form(""),
    smtp_port:    int           = Form(587),
    smtp_user:    str           = Form(""),
    smtp_password: str          = Form(""),
    smtp_from:    str           = Form(""),
    smtp_tls:     str           = Form(""),
    app_base_url: str | None    = Form(None),
    _admin: dict = Depends(require_admin),
):
    lang = get_lang(request)
    cfg  = _read_smtp()

    cfg["smtp_host"]    = smtp_host.strip()
    cfg["smtp_port"]    = smtp_port
    cfg["smtp_user"]    = smtp_user.strip()
    cfg["smtp_from"]    = smtp_from.strip()
    cfg["smtp_tls"]     = smtp_tls == "1"
    # Preserva URL base se o campo não veio no formulário (agora fica em Geral)
    if app_base_url is not None:
        cfg["app_base_url"] = app_base_url.strip().rstrip("/")

    # Só sobrescreve a senha se o usuário digitou algo novo
    if smtp_password.strip():
        cfg["smtp_password"] = smtp_password.strip()

    _write_smtp(cfg)
    # Atualiza estado em memória com senha decifrada para uso no send_email
    request.app.state.smtp_settings = cfg

    logger.info("[Portal] Configurações SMTP salvas.")
    resp = _settings_redirect("email", "smtp_saved")
    return set_lang_cookie(resp, lang)


# ──────────────────────────────────────────────────────────────
# POST /settings/smtp/test — enviar email de teste
# ──────────────────────────────────────────────────────────────

@router.post("/smtp/test")
async def test_smtp(
    request: Request,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    lang    = get_lang(request)
    user    = _admin
    cfg     = _read_smtp()

    # Envia para o email do admin logado
    admin_obj = db.query(User).filter(User.id == user["id"]).first()
    to_email  = admin_obj.email if admin_obj else user.get("email", "")

    try:
        send_test_email(to_email, cfg)
        import urllib.parse
        resp = _settings_redirect("email", "smtp_test_ok", f"to={urllib.parse.quote(to_email)}")
    except Exception as exc:
        logger.error(f"[Portal] Falha no teste SMTP: {exc}")
        import urllib.parse
        resp = _settings_redirect("email", "smtp_test_fail", f"err={urllib.parse.quote(str(exc))}")

    return set_lang_cookie(resp, lang)


# ──────────────────────────────────────────────────────────────
# POST /settings/footer — salvar dados do rodapé
# ──────────────────────────────────────────────────────────────

@router.post("/footer")
async def save_footer(
    request: Request,
    db: Session = Depends(get_db),
    nome_institucional: str = Form(""),
    endereco:           str = Form(""),
    link_estatuto:      str = Form(""),
    link_repositorio:   str = Form(""),
    _admin: dict = Depends(require_admin),
):
    lang = get_lang(request)

    cfg = db.query(Configuracao).filter(Configuracao.id == 1).first()
    if cfg is None:
        cfg = Configuracao(id=1)
        db.add(cfg)

    cfg.nome_institucional = nome_institucional.strip()
    cfg.endereco           = endereco.strip()
    cfg.link_estatuto      = link_estatuto.strip()
    cfg.link_repositorio   = link_repositorio.strip()
    db.commit()
    db.refresh(cfg)

    data = cfg.to_dict()
    _cache_del_footer(_redis(request))
    _cache_set_footer(_redis(request), data)
    request.app.state.footer_config = data

    logger.info("[Portal] Configurações do rodapé salvas.")
    resp = _settings_redirect("aparencia", "footer_saved")
    return set_lang_cookie(resp, lang)


@router.post("/idioma")
async def save_idioma(
    request: Request,
    db: Session = Depends(get_db),
    idioma: str = Form("pt"),
    _admin: dict = Depends(require_admin),
):
    """Define o idioma global da aplicação (apenas admin). Compat: redireciona para geral."""
    return await save_geral(request, db, idioma=idioma, app_base_url=None, _admin=_admin)


@router.post("/geral")
async def save_geral(
    request: Request,
    db: Session = Depends(get_db),
    idioma: str = Form("pt"),
    app_base_url: str | None = Form(None),
    _admin: dict = Depends(require_admin),
):
    """Idioma global + URL base da aplicação."""
    lang = (idioma or "pt").strip().lower()
    if lang not in {"pt", "en", "es"}:
        lang = "pt"

    cfg = db.query(Configuracao).filter(Configuracao.id == 1).first()
    if cfg is None:
        cfg = Configuracao(id=1, idioma=lang)
        db.add(cfg)
    else:
        cfg.idioma = lang
    db.commit()
    db.refresh(cfg)

    data = cfg.to_dict()
    _cache_del_footer(_redis(request))
    _cache_set_footer(_redis(request), data)
    request.app.state.footer_config = data
    request.app.state.app_lang = lang

    if app_base_url is not None:
        smtp_cfg = _read_smtp()
        smtp_cfg["app_base_url"] = app_base_url.strip().rstrip("/")
        _write_smtp(smtp_cfg)
        request.app.state.smtp_settings = smtp_cfg

    logger.info("[Portal] Configurações gerais salvas (idioma=%s)", lang)
    resp = _settings_redirect("geral", "geral_saved")
    return set_lang_cookie(resp, lang)


@router.post("/auditoria/retencao")
async def save_audit_retention(
    request: Request,
    db: Session = Depends(get_db),
    audit_retention_days: int = Form(90),
    _admin: dict = Depends(require_admin),
):
    from app.audit import clamp_retention_days, audit_from_request, purge_expired_logs

    days = clamp_retention_days(audit_retention_days)
    cfg = db.query(Configuracao).filter(Configuracao.id == 1).first()
    if cfg is None:
        cfg = Configuracao(id=1, audit_retention_days=days)
        db.add(cfg)
    else:
        cfg.audit_retention_days = days
    db.commit()
    db.refresh(cfg)

    data = cfg.to_dict()
    _cache_del_footer(_redis(request))
    _cache_set_footer(_redis(request), data)
    request.app.state.footer_config = data

    audit_from_request(
        request,
        action="settings.audit_retention",
        entity_type="configuracao",
        entity_id="1",
        summary=f"Retenção de auditoria definida para {days} dia(s)",
        meta={"audit_retention_days": days},
    )
    # Aplica imediatamente a nova janela
    purge_expired_logs(days)

    logger.info("[Portal] Retenção de auditoria: %s dias", days)
    resp = _settings_redirect("sistema", "retention_saved")
    return set_lang_cookie(resp, get_lang(request))


@router.post("/pwa")
async def save_pwa(
    request: Request,
    db: Session = Depends(get_db),
    pwa_enabled: str = Form("0"),
    _admin: dict = Depends(require_admin),
):
    from app.audit import audit_from_request

    enabled = str(pwa_enabled).strip() in {"1", "true", "on", "yes"}
    cfg = db.query(Configuracao).filter(Configuracao.id == 1).first()
    if cfg is None:
        cfg = Configuracao(id=1, pwa_enabled=enabled)
        db.add(cfg)
    else:
        cfg.pwa_enabled = enabled
    db.commit()
    db.refresh(cfg)

    data = cfg.to_dict()
    _cache_del_footer(_redis(request))
    _cache_set_footer(_redis(request), data)
    request.app.state.footer_config = data

    audit_from_request(
        request,
        action="settings.pwa",
        entity_type="configuracao",
        entity_id="1",
        summary=f"Site mobile / PWA {'ligado' if enabled else 'desligado'}",
        meta={"pwa_enabled": enabled},
    )
    logger.info("[Portal] PWA enabled=%s", enabled)
    resp = _settings_redirect("sistema", "pwa_saved")
    return set_lang_cookie(resp, get_lang(request))


@router.get("/auditoria", response_class=HTMLResponse)
async def audit_log_page(
    request: Request,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
    page: int = 1,
    q: str = "",
    action: str = "",
):
    from app.models import AuditLog
    from app.audit import get_retention_days, AUDIT_RETENTION_MIN, AUDIT_RETENTION_MAX

    page = max(1, page)
    per_page = 50
    query = db.query(AuditLog)
    q = (q or "").strip()
    action = (action or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(
            (AuditLog.actor_username.ilike(like))
            | (AuditLog.summary.ilike(like))
            | (AuditLog.entity_type.ilike(like))
            | (AuditLog.entity_id.ilike(like))
        )
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))

    total = query.count()
    pages = max(1, (total + per_page - 1) // per_page)
    if page > pages:
        page = pages
    rows = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    ctx = make_ctx(request, {
        "audit_rows": rows,
        "page": page,
        "pages": pages,
        "total": total,
        "q": q,
        "action_filter": action,
        "retention_days": get_retention_days(db),
        "retention_min": AUDIT_RETENTION_MIN,
        "retention_max": AUDIT_RETENTION_MAX,
    })
    resp = templates.TemplateResponse("settings/auditoria.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


# ──────────────────────────────────────────────────────────────
# Exportação de dados
# ──────────────────────────────────────────────────────────────

_EXPORT_HEADERS = [
    "id", "nome", "email", "celular", "telefone",
    "data_nascimento", "idade", "papeis", "instrumentos",
    "ativo", "criado_em",
]


def _get_all_musicians(db: Session) -> list[dict]:
    rows = []
    for m in db.query(Musician).order_by(Musician.first_name).all():
        rows.append({
            "id":               m.id,
            "nome":             m.full_name,
            "email":            m.email,
            "celular":          m.celular or m.phone or "",
            "telefone":         m.telefone or "",
            "data_nascimento":  m.birth_date.isoformat() if m.birth_date else "",
            "idade":            m.age if m.birth_date else "",
            "papeis":           ", ".join(r.label for r in m.roles) if m.roles else "",
            "instrumentos":     ", ".join(i.nome for i in m.instruments) if m.instruments else "",
            "ativo":            "Sim" if m.is_active else "Não",
            "criado_em":        m.created_at.strftime("%d/%m/%Y %H:%M") if m.created_at else "",
        })
    return rows


@router.get("/export")
async def export_data(
    request: Request,
    db: Session = Depends(get_db),
    format: str = "xlsx",
    _admin: dict = Depends(require_admin),
):
    rows = _get_all_musicians(db)
    ts   = datetime.now().strftime("%Y%m%d_%H%M")

    # ── CSV ──────────────────────────────────────────────────
    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_EXPORT_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8-sig")]),  # BOM para Excel
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=membros_{ts}.csv"},
        )

    # ── JSON ─────────────────────────────────────────────────
    if format == "json":
        payload = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
        return StreamingResponse(
            iter([payload]),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=membros_{ts}.json"},
        )

    # ── XLSX (padrão) ─────────────────────────────────────────
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Membros"

    header_fill = PatternFill("solid", fgColor="1A365C")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    header_align = Alignment(horizontal="center", vertical="center")

    col_widths = {
        "id": 6, "nome": 30, "email": 32, "celular": 16, "telefone": 16,
        "data_nascimento": 16, "idade": 8, "papeis": 28, "instrumentos": 36,
        "ativo": 8, "criado_em": 18,
    }

    for col_idx, header in enumerate(_EXPORT_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header.upper().replace("_", " "))
        cell.fill   = header_fill
        cell.font   = header_font
        cell.alignment = header_align
        ws.column_dimensions[
            openpyxl.utils.get_column_letter(col_idx)
        ].width = col_widths.get(header, 14)

    ws.row_dimensions[1].height = 22

    for row_idx, row in enumerate(rows, start=2):
        for col_idx, key in enumerate(_EXPORT_HEADERS, start=1):
            ws.cell(row=row_idx, column=col_idx, value=row.get(key, ""))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=membros_{ts}.xlsx"},
    )


# ──────────────────────────────────────────────────────────────
# Exportação do Inventário de Patrimônio
# ──────────────────────────────────────────────────────────────

_PATRIMONIO_HEADERS = [
    "identificador", "tipo", "fabricante", "modelo", "instrumento",
    "status", "valor_mercado", "ano_compra", "musico_responsavel",
    "data_emprestimo", "observacoes", "qr_url", "criado_em",
]


def _get_all_patrimonio(db: Session, base_url: str = "") -> list[dict]:
    rows = []
    for item in db.query(Patrimonio).order_by(Patrimonio.created_at).all():
        det = item.detalhes or {}
        emp = item.emprestimo_ativo
        instrumento = det.get("instrumento_nome") or ""
        if not instrumento and item.tipo_item == TipoItem.Partitura:
            instrumento = det.get("nome_obra", "")
        rows.append({
            "identificador":    item.identificador_interno,
            "tipo":             _PATRIMONIO_TIPO_LABEL.get(item.tipo_item, item.tipo_item.value),
            "fabricante":       item.fabricante or "",
            "modelo":           item.modelo or "",
            "instrumento":      instrumento,
            "status":           _PATRIMONIO_STATUS_LABEL.get(item.status, item.status.value),
            "valor_mercado":    float(item.valor_mercado) if item.valor_mercado else "",
            "ano_compra":       item.ano_compra or "",
            "musico_responsavel": emp.musician.full_name if emp else "",
            "data_emprestimo":  emp.data_emprestimo.strftime("%d/%m/%Y") if emp else "",
            "observacoes":      item.observacoes or "",
            "qr_url":           f"{base_url}/patrimonio/qr/{item.identificador_interno}",
            "criado_em":        item.created_at.strftime("%d/%m/%Y %H:%M") if item.created_at else "",
        })
    return rows


@router.get("/export-patrimonio")
async def export_patrimonio(
    request: Request,
    db: Session = Depends(get_db),
    format: str = "xlsx",
    _admin: dict = Depends(require_admin),
):
    cfg      = _read_smtp()
    base_url = cfg.get("app_base_url", "").rstrip("/")
    rows     = _get_all_patrimonio(db, base_url)
    ts       = datetime.now().strftime("%Y%m%d_%H%M")

    # ── CSV ──────────────────────────────────────────────────
    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_PATRIMONIO_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=inventario_{ts}.csv"},
        )

    # ── JSON ─────────────────────────────────────────────────
    if format == "json":
        payload = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
        return StreamingResponse(
            iter([payload]),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=inventario_{ts}.json"},
        )

    # ── XLSX (padrão) ─────────────────────────────────────────
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventário"

    header_fill  = PatternFill("solid", fgColor="1A365C")
    header_font  = Font(color="FFFFFF", bold=True, size=11)
    header_align = Alignment(horizontal="center", vertical="center")

    col_widths = {
        "identificador": 20, "tipo": 14, "fabricante": 22, "modelo": 22,
        "instrumento": 26, "status": 14, "valor_mercado": 14, "ano_compra": 12,
        "musico_responsavel": 28, "data_emprestimo": 16, "observacoes": 30,
        "qr_url": 50, "criado_em": 18,
    }

    header_labels = {
        "identificador": "IDENTIFICADOR", "tipo": "TIPO", "fabricante": "FABRICANTE",
        "modelo": "MODELO", "instrumento": "INSTRUMENTO", "status": "STATUS",
        "valor_mercado": "VALOR (R$)", "ano_compra": "ANO COMPRA",
        "musico_responsavel": "RESPONSÁVEL", "data_emprestimo": "DATA EMPRÉSTIMO",
        "observacoes": "OBSERVAÇÕES", "qr_url": "QR / URL", "criado_em": "CADASTRADO EM",
    }

    for col_idx, key in enumerate(_PATRIMONIO_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header_labels.get(key, key.upper()))
        cell.fill      = header_fill
        cell.font      = header_font
        cell.alignment = header_align
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = col_widths.get(key, 16)

    ws.row_dimensions[1].height = 22

    for row_idx, row in enumerate(rows, start=2):
        for col_idx, key in enumerate(_PATRIMONIO_HEADERS, start=1):
            ws.cell(row=row_idx, column=col_idx, value=row.get(key, ""))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=inventario_{ts}.xlsx"},
    )


# ──────────────────────────────────────────────────────────────
# Exportação de Aniversariantes
# ──────────────────────────────────────────────────────────────

_BIRTHDAY_HEADERS = ["nome", "email", "celular", "data_nascimento", "dia", "papeis", "instrumentos"]

_MESES_FILENAME = [
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _get_aniversariantes(db: Session, month: int) -> list[dict]:
    musicians = (
        db.query(Musician)
        .filter(
            Musician.is_active == True,
            extract("month", Musician.birth_date) == month,
        )
        .order_by(extract("day", Musician.birth_date))
        .all()
    )
    return [
        {
            "nome":            m.full_name,
            "email":           m.email,
            "celular":         m.celular or m.phone or "",
            "data_nascimento": m.birth_date.strftime("%d/%m/%Y") if m.birth_date else "",
            "dia":             m.birth_date.day if m.birth_date else "",
            "papeis":          ", ".join(r.label for r in m.roles) if m.roles else "",
            "instrumentos":    ", ".join(i.nome for i in m.instruments) if m.instruments else "",
        }
        for m in musicians
    ]


@router.get("/export-aniversariantes")
async def export_aniversariantes(
    request: Request,
    db: Session = Depends(get_db),
    month: int = 0,
    format: str = "xlsx",
    _admin: dict = Depends(require_admin),
):
    if not 1 <= month <= 12:
        month = date.today().month

    rows    = _get_aniversariantes(db, month)
    mes_str = _MESES_FILENAME[month - 1]
    ts      = f"{mes_str}_{date.today().year}"

    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_BIRTHDAY_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=aniversariantes_{ts}.csv"},
        )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Aniversariantes"

    header_fill  = PatternFill("solid", fgColor="1A365C")
    header_font  = Font(color="FFFFFF", bold=True, size=11)
    header_align = Alignment(horizontal="center", vertical="center")
    today_fill   = PatternFill("solid", fgColor="FFF3CD")

    col_widths = {
        "nome": 30, "email": 32, "celular": 16,
        "data_nascimento": 16, "dia": 6, "papeis": 28, "instrumentos": 36,
    }
    header_labels = {
        "nome": "NOME", "email": "EMAIL", "celular": "CELULAR",
        "data_nascimento": "NASCIMENTO", "dia": "DIA",
        "papeis": "PAPÉIS", "instrumentos": "INSTRUMENTOS",
    }

    for col_idx, key in enumerate(_BIRTHDAY_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header_labels.get(key, key.upper()))
        cell.fill      = header_fill
        cell.font      = header_font
        cell.alignment = header_align
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = col_widths.get(key, 14)

    ws.row_dimensions[1].height = 22

    today_day = date.today().day if month == date.today().month else None
    for row_idx, row in enumerate(rows, start=2):
        for col_idx, key in enumerate(_BIRTHDAY_HEADERS, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=row.get(key, ""))
            if today_day and row.get("dia") == today_day:
                cell.fill = today_fill

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=aniversariantes_{ts}.xlsx"},
    )


# ──────────────────────────────────────────────────────────────
# GET /settings/health — verificação de saúde dos serviços
# ──────────────────────────────────────────────────────────────

@router.get("/health", response_class=JSONResponse)
async def health_check(request: Request, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    from sqlalchemy import text as sa_text

    services = {}

    # ── PostgreSQL ───────────────────────────────────────────
    try:
        db.execute(sa_text("SELECT 1"))
        itens      = db.execute(sa_text("SELECT count(*) FROM patrimonio")).scalar() or 0
        etiquetas  = db.execute(sa_text("SELECT count(*) FROM patrimonio_etiqueta WHERE ativo = true")).scalar() or 0
        membros    = db.execute(sa_text("SELECT count(*) FROM musicians WHERE is_active = true")).scalar() or 0
        services["database"] = {
            "status": "ok",
            "label":  "PostgreSQL 15",
            "detail": f"{membros} membros · {itens} itens no inventário · {etiquetas} etiquetas ativas",
        }
    except Exception as exc:
        services["database"] = {"status": "error", "label": "PostgreSQL 15", "detail": str(exc)}

    # ── Redis ────────────────────────────────────────────────
    r = getattr(request.app.state, "redis", None)
    if r:
        try:
            r.ping()
            services["cache"] = {"status": "ok", "label": "Redis 7", "detail": "Cache ativo"}
        except Exception as exc:
            services["cache"] = {"status": "error", "label": "Redis 7", "detail": str(exc)}
    else:
        services["cache"] = {
            "status": "degraded",
            "label":  "Redis 7",
            "detail": "Indisponível — operando sem cache (dados servidos direto do banco)",
        }

    # ── Aplicação ────────────────────────────────────────────
    services["app"] = {
        "status": "ok",
        "label":  "Aplicação",
        "detail": f"Versão {request.app.state.app_version}",
    }

    overall = "ok" if all(s["status"] == "ok" for s in services.values()) else (
        "degraded" if all(s["status"] != "error" for s in services.values()) else "error"
    )
    return JSONResponse(content={"status": overall, "services": services})
