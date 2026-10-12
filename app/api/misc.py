"""API v1 — settings, search, release notes, i18n."""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import openpyxl
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl.styles import Alignment, Font, PatternFill
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import require_api_admin, require_system_user, user_permissions
from app.database import get_db
from app.email_utils import send_test_email
from app.models import Configuracao, Musician, Obra, Patrimonio, ReleaseNote, User
from app.routers.settings import (
    ALLOWED_LOGO_EXT,
    MAX_LOGO_SIZE,
    UPLOAD_DIR,
    _BIRTHDAY_HEADERS,
    _EXPORT_HEADERS,
    _MESES_FILENAME,
    _PATRIMONIO_HEADERS,
    _get_all_musicians,
    _get_all_patrimonio,
    _get_aniversariantes,
    _read_branding,
    _read_smtp,
    _smtp_safe,
    _validate_logo,
    _write_branding,
    _write_smtp,
)

settings_router = APIRouter(prefix="/settings", tags=["Settings"])
search_router = APIRouter(prefix="/search", tags=["Search"])
releases_router = APIRouter(prefix="/release-notes", tags=["Release Notes"])
i18n_router = APIRouter(prefix="/i18n", tags=["i18n"])


def _get_or_create_config(db: Session) -> Configuracao:
    cfg = db.query(Configuracao).filter(Configuracao.id == 1).first()
    if not cfg:
        cfg = Configuracao(id=1)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _cfg_public(cfg: Configuracao) -> dict:
    data = cfg.to_dict()
    smtp = _read_smtp()
    data["app_base_url"] = smtp.get("app_base_url") or ""
    branding = _read_branding()
    data["logo"] = branding.get("logo")
    return data


class SettingsUpdate(BaseModel):
    nome_institucional: Optional[str] = None
    endereco: Optional[str] = None
    link_estatuto: Optional[str] = None
    link_repositorio: Optional[str] = None
    idioma: Optional[str] = Field(None, pattern="^(pt|en|es)$")
    audit_retention_days: Optional[int] = Field(None, ge=7, le=90)
    pwa_enabled: Optional[bool] = None
    app_base_url: Optional[str] = None


class SmtpUpdate(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_tls: Optional[bool] = None
    smtp_password: Optional[str] = None
    app_base_url: Optional[str] = None


class SmtpTestBody(BaseModel):
    to: Optional[str] = None


@settings_router.get("")
async def get_settings(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_system_user),
):
    cfg = _get_or_create_config(db)
    public = _cfg_public(cfg)
    footer = getattr(request.app.state, "footer_config", None) or public
    return {
        "config": public,
        "footer": footer,
        "permissions": user_permissions(user),
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        },
    }


@settings_router.put("")
async def update_settings(
    body: SettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_admin),
):
    cfg = _get_or_create_config(db)
    data = body.model_dump(exclude_unset=True)
    app_base_url = data.pop("app_base_url", None)
    for k, v in data.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    db.commit()
    db.refresh(cfg)

    if app_base_url is not None:
        smtp_cfg = _read_smtp()
        smtp_cfg["app_base_url"] = (app_base_url or "").strip().rstrip("/")
        _write_smtp(smtp_cfg)
        request.app.state.smtp_settings = smtp_cfg

    public = _cfg_public(cfg)
    request.app.state.footer_config = {k: v for k, v in public.items() if k not in {"app_base_url", "logo"}}
    request.app.state.app_lang = public.get("idioma") or "pt"
    return {"config": public}


@settings_router.get("/smtp")
async def get_smtp(_: User = Depends(require_api_admin)):
    return _smtp_safe(_read_smtp())


@settings_router.put("/smtp")
async def update_smtp(
    body: SmtpUpdate,
    request: Request,
    _: User = Depends(require_api_admin),
):
    cfg = _read_smtp()
    data = body.model_dump(exclude_unset=True)
    password = data.pop("smtp_password", None)
    for k, v in data.items():
        if k == "app_base_url" and isinstance(v, str):
            cfg[k] = v.strip().rstrip("/")
        elif k == "smtp_host" or k == "smtp_user" or k == "smtp_from":
            cfg[k] = (v or "").strip() if isinstance(v, str) else v
        else:
            cfg[k] = v
    if password is not None and str(password).strip():
        cfg["smtp_password"] = str(password).strip()
    _write_smtp(cfg)
    request.app.state.smtp_settings = cfg
    return _smtp_safe(cfg)


@settings_router.post("/smtp/test")
async def test_smtp(
    body: SmtpTestBody = SmtpTestBody(),
    db: Session = Depends(get_db),
    user: User = Depends(require_api_admin),
):
    cfg = _read_smtp()
    to_email = (body.to or "").strip() or user.email
    if not to_email:
        raise HTTPException(400, "Informe um e-mail de destino.")
    try:
        send_test_email(to_email, cfg)
    except Exception as exc:
        raise HTTPException(400, f"Falha no envio: {exc}") from exc
    return {"ok": True, "to": to_email}


@settings_router.post("/logo")
async def upload_logo(
    request: Request,
    logo: UploadFile = File(...),
    _: User = Depends(require_api_admin),
):
    ext = Path(logo.filename).suffix.lower() if logo.filename else ""
    if ext not in ALLOWED_LOGO_EXT:
        raise HTTPException(400, f"Formato não suportado: {ext or '(sem extensão)'}. Use PNG, JPG, SVG ou WebP.")
    data = await logo.read()
    if len(data) == 0:
        raise HTTPException(400, "Arquivo vazio.")
    if len(data) > MAX_LOGO_SIZE:
        raise HTTPException(400, "Arquivo muito grande. Limite: 2 MB.")
    if not _validate_logo(data, ext):
        raise HTTPException(400, "Conteúdo do arquivo não corresponde ao formato declarado.")

    branding = _read_branding()
    old_logo = branding.get("logo")
    if old_logo:
        old_path = UPLOAD_DIR / old_logo
        if old_path.exists():
            old_path.unlink()

    filename = f"logo_{uuid.uuid4()}{ext}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / filename).write_bytes(data)
    branding["logo"] = filename
    _write_branding(branding)
    request.app.state.branding = branding
    return {"ok": True, "logo": filename}


@settings_router.post("/logo/remove")
async def remove_logo(
    request: Request,
    _: User = Depends(require_api_admin),
):
    branding = _read_branding()
    old_logo = branding.pop("logo", None)
    if old_logo:
        old_path = UPLOAD_DIR / old_logo
        if old_path.exists():
            old_path.unlink()
    _write_branding(branding)
    request.app.state.branding = branding
    return {"ok": True}


@settings_router.get("/export")
async def export_members(
    format: str = "xlsx",
    db: Session = Depends(get_db),
    _: User = Depends(require_api_admin),
):
    rows = _get_all_musicians(db)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_EXPORT_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=membros_{ts}.csv"},
        )
    if format == "json":
        payload = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
        return StreamingResponse(
            iter([payload]),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=membros_{ts}.json"},
        )
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Membros"
    header_fill = PatternFill("solid", fgColor="1A365C")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    header_align = Alignment(horizontal="center", vertical="center")
    for col_idx, header in enumerate(_EXPORT_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header.upper().replace("_", " "))
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align
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


@settings_router.get("/export-patrimonio")
async def export_patrimonio(
    format: str = "xlsx",
    db: Session = Depends(get_db),
    _: User = Depends(require_api_admin),
):
    cfg = _read_smtp()
    base_url = (cfg.get("app_base_url") or "").rstrip("/")
    rows = _get_all_patrimonio(db, base_url)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
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
    if format == "json":
        payload = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
        return StreamingResponse(
            iter([payload]),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=inventario_{ts}.json"},
        )
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventário"
    header_fill = PatternFill("solid", fgColor="1A365C")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    for col_idx, header in enumerate(_PATRIMONIO_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header.upper().replace("_", " "))
        cell.fill = header_fill
        cell.font = header_font
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


@settings_router.get("/export-aniversariantes")
async def export_aniversariantes(
    month: int = 0,
    format: str = "xlsx",
    db: Session = Depends(get_db),
    _: User = Depends(require_api_admin),
):
    if not 1 <= month <= 12:
        month = date.today().month
    rows = _get_aniversariantes(db, month)
    mes_str = _MESES_FILENAME[month - 1]
    ts = f"{mes_str}_{date.today().year}"
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
    header_fill = PatternFill("solid", fgColor="1A365C")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    today_fill = PatternFill("solid", fgColor="FFF3CD")
    for col_idx, key in enumerate(_BIRTHDAY_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=key.upper())
        cell.fill = header_fill
        cell.font = header_font
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


@settings_router.get("/health")
async def health_check(request: Request, db: Session = Depends(get_db), _: User = Depends(require_api_admin)):
    from sqlalchemy import text as sa_text

    services = {}
    try:
        db.execute(sa_text("SELECT 1"))
        itens = db.execute(sa_text("SELECT count(*) FROM patrimonio")).scalar() or 0
        etiquetas = db.execute(sa_text("SELECT count(*) FROM patrimonio_etiqueta WHERE ativo = true")).scalar() or 0
        membros = db.execute(sa_text("SELECT count(*) FROM musicians WHERE is_active = true")).scalar() or 0
        services["database"] = {
            "status": "ok",
            "label": "PostgreSQL 15",
            "detail": f"{membros} membros · {itens} itens no inventário · {etiquetas} etiquetas ativas",
        }
    except Exception as exc:
        services["database"] = {"status": "error", "label": "PostgreSQL 15", "detail": str(exc)}

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
            "label": "Redis 7",
            "detail": "Indisponível — operando sem cache (dados servidos direto do banco)",
        }

    services["app"] = {
        "status": "ok",
        "label": "Aplicação",
        "detail": f"Versão {getattr(request.app.state, 'app_version', '?')}",
    }

    overall = (
        "ok"
        if all(s["status"] == "ok" for s in services.values())
        else ("degraded" if all(s["status"] != "error" for s in services.values()) else "error")
    )
    return {"status": overall, "services": services}


@search_router.get("")
async def global_search(
    q: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    q = q.strip()
    if len(q) < 2:
        return {"musicians": [], "patrimonio": [], "obras": []}
    term = f"%{q}%"
    musicians = (
        db.query(Musician)
        .filter(
            or_(
                Musician.first_name.ilike(term),
                Musician.last_name.ilike(term),
                Musician.email.ilike(term),
                Musician.apelido.ilike(term),
            )
        )
        .limit(6)
        .all()
    )
    patrimonio = (
        db.query(Patrimonio)
        .filter(
            or_(
                Patrimonio.identificador_interno.ilike(term),
                Patrimonio.fabricante.ilike(term),
                Patrimonio.modelo.ilike(term),
            )
        )
        .limit(6)
        .all()
    )
    obras = (
        db.query(Obra)
        .filter(
            or_(
                Obra.titulo.ilike(term),
                Obra.titulo_original.ilike(term),
                Obra.compositor_nome.ilike(term),
            )
        )
        .limit(6)
        .all()
    )
    return {
        "musicians": [
            {"id": m.id, "name": m.full_name, "email": m.email, "is_active": m.is_active, "url": f"/musicians/{m.id}"}
            for m in musicians
        ],
        "patrimonio": [
            {
                "id": str(p.id),
                "identificador": p.identificador_interno,
                "tipo": p.tipo_label,
                "fabricante": p.fabricante or "",
                "modelo": p.modelo or "",
                "url": f"/patrimonio/{p.id}",
            }
            for p in patrimonio
        ],
        "obras": [
            {"id": o.id, "titulo": o.titulo, "compositor": o.compositor_label, "url": f"/acervo/obras/{o.id}"}
            for o in obras
        ],
    }


@releases_router.get("")
async def list_releases(
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
    limit: int = Query(20, ge=1, le=100),
):
    notes = db.query(ReleaseNote).order_by(ReleaseNote.released_at.desc()).limit(limit).all()
    return {
        "items": [
            {
                "id": n.id,
                "version": n.version,
                "title": n.title,
                "body": n.notes,
                "released_at": n.released_at.isoformat() if n.released_at else None,
                "is_current": n.is_current,
            }
            for n in notes
        ]
    }


class ReleaseIn(BaseModel):
    version: str = Field(..., min_length=1, max_length=32)
    title: str = ""
    body: str = ""
    released_at: Optional[str] = None
    is_current: bool = False


@releases_router.post("", status_code=201)
async def create_release(
    body: ReleaseIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_api_admin),
):
    from datetime import date as date_cls

    if db.query(ReleaseNote).filter(ReleaseNote.version == body.version.strip()).first():
        raise HTTPException(400, "Versão já existe.")
    released = date_cls.today()
    if body.released_at:
        released = date_cls.fromisoformat(body.released_at[:10])
    if body.is_current:
        db.query(ReleaseNote).update({ReleaseNote.is_current: False})
    n = ReleaseNote(
        version=body.version.strip(),
        title=body.title or "",
        notes=body.body or "",
        released_at=released,
        is_current=body.is_current,
        created_by=user.id,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return {"id": n.id, "version": n.version}


@releases_router.put("/{note_id}")
async def update_release(
    note_id: int,
    body: ReleaseIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_admin),
):
    from datetime import date as date_cls

    n = db.query(ReleaseNote).filter(ReleaseNote.id == note_id).first()
    if not n:
        raise HTTPException(404, "Não encontrado.")
    if body.is_current:
        db.query(ReleaseNote).update({ReleaseNote.is_current: False})
    n.version = body.version.strip()
    n.title = body.title or ""
    n.notes = body.body or ""
    if body.released_at:
        n.released_at = date_cls.fromisoformat(body.released_at[:10])
    n.is_current = body.is_current
    db.commit()
    return {"ok": True}


@releases_router.delete("/{note_id}")
async def delete_release(note_id: int, db: Session = Depends(get_db), _: User = Depends(require_api_admin)):
    n = db.query(ReleaseNote).filter(ReleaseNote.id == note_id).first()
    if not n:
        raise HTTPException(404, "Não encontrado.")
    db.delete(n)
    db.commit()
    return {"ok": True}


@settings_router.get("/audit")
async def list_audit(
    db: Session = Depends(get_db),
    _: User = Depends(require_api_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str = "",
    action: str = "",
):
    from app.models import AuditLog

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
    rows = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "actor_username": r.actor_username,
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "summary": r.summary,
            }
            for r in rows
        ],
    }


@i18n_router.get("/{lang}")
async def get_i18n(lang: str, request: Request):
    if lang not in {"pt", "en", "es"}:
        raise HTTPException(400, "Idioma inválido.")
    translations = getattr(request.app.state, "translations", {}) or {}
    return translations.get(lang) or translations.get("pt") or {}
