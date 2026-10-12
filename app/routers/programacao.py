"""
Portal — Router de Programação Musical.
Gerencia eventos (ex-Concertos), calendário interno, feed iCal e distribuição de partituras.
"""

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session
from pathlib import Path

from app.database import get_db
from app.dependencies import make_ctx, set_lang_cookie, require_manage_acervo
from app.models import (
    Concerto, ConcertoArranjo, ConcertoAcessoPartitura,
    Arranjo, ArranjoDocumento, Obra, Musician, MemberRole, RoleType,
)
from app.distribuicao import sugerir_distribuicao, criar_ou_atualizar_acessos
from app.email_utils import send_partituras_evento

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/acervo/programacao")
templates = Jinja2Templates(directory="templates")


def _parse_int(val) -> int | None:
    try:
        return int(str(val).strip()) if val and str(val).strip() else None
    except ValueError:
        return None


def _membros_maestros(db: Session) -> list:
    return (
        db.query(Musician)
        .filter(
            Musician.is_active == True,
            Musician.roles.any(MemberRole.role_type == RoleType.maestro)
        )
        .order_by(Musician.first_name, Musician.last_name)
        .all()
    )


# ══════════════════════════════════════════════════════════════
# CALENDÁRIO INTERNO — FullCalendar
# ══════════════════════════════════════════════════════════════

@router.get("/calendario", response_class=HTMLResponse)
def calendario_interno(request: Request, db: Session = Depends(get_db)):
    ctx = make_ctx(request, {})
    resp = templates.TemplateResponse("acervo/calendario_interno.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.get("/eventos.json")
def eventos_json(
    start: str = None,
    end: str = None,
    db: Session = Depends(get_db),
):
    """API FullCalendar — retorna eventos no intervalo solicitado."""
    query_params: dict = {}
    where_clauses = []

    if start:
        try:
            dt_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            where_clauses.append("c.data_inicio >= :start")
            query_params["start"] = dt_start
        except ValueError:
            pass
    if end:
        try:
            dt_end = datetime.fromisoformat(end.replace("Z", "+00:00"))
            where_clauses.append("c.data_inicio <= :end")
            query_params["end"] = dt_end
        except ValueError:
            pass

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    rows = db.execute(text(f"""
        SELECT c.id, c.titulo, c.data_inicio, c.data_fim,
               c.local, c.publico, c.maestro_id,
               m.first_name || ' ' || m.last_name AS maestro_nome,
               COUNT(ca.id) AS num_obras
        FROM concertos c
        LEFT JOIN musicians m ON m.id = c.maestro_id
        LEFT JOIN concerto_arranjos ca ON ca.concerto_id = c.id
        {where_sql}
        GROUP BY c.id, m.first_name, m.last_name
        ORDER BY c.data_inicio
    """), query_params).fetchall()

    events = []
    for r in rows:
        dt_start = r.data_inicio
        if dt_start and dt_start.tzinfo is None:
            dt_start = dt_start.replace(tzinfo=timezone.utc)
        dt_end = r.data_fim or r.data_inicio
        if dt_end and dt_end.tzinfo is None:
            dt_end = dt_end.replace(tzinfo=timezone.utc)

        desc_parts = []
        if r.maestro_nome:
            desc_parts.append(f"Maestro(a): {r.maestro_nome}")
        if r.local:
            desc_parts.append(r.local)
        if r.num_obras:
            desc_parts.append(f"{r.num_obras} obra(s)")

        events.append({
            "id":    str(r.id),
            "title": r.titulo,
            "start": dt_start.isoformat() if dt_start else None,
            "end":   dt_end.isoformat()   if dt_end   else None,
            "url":   f"/acervo/programacao/{r.id}",
            "backgroundColor": "#4f6ef7" if r.publico else "#94a3b8",
            "borderColor":     "#3b5bdb" if r.publico else "#64748b",
            "extendedProps": {
                "local":      r.local or "",
                "maestro":    r.maestro_nome or "",
                "num_obras":  r.num_obras or 0,
                "descricao":  "\n".join(desc_parts),
            },
        })
    return JSONResponse(content=events)


# ── Redirect raiz para calendário ─────────────────────────────

@router.get("", response_class=HTMLResponse)
def programacao_home(request: Request):
    return RedirectResponse(url="/acervo/programacao/calendario", status_code=302)


# ══════════════════════════════════════════════════════════════
# LISTA DE EVENTOS
# ══════════════════════════════════════════════════════════════

@router.get("/lista", response_class=HTMLResponse)
def programacao_list(request: Request, db: Session = Depends(get_db)):
    eventos = db.query(Concerto).order_by(Concerto.data_inicio.desc()).all()
    ctx = make_ctx(request, {"eventos": eventos})
    resp = templates.TemplateResponse("acervo/programacao_list.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


# ══════════════════════════════════════════════════════════════
# CRUD DE EVENTOS
# ══════════════════════════════════════════════════════════════

@router.get("/new", response_class=HTMLResponse)
def evento_new_form(
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_manage_acervo),
):
    ctx = make_ctx(request, {
        "evento": None,
        "maestros": _membros_maestros(db),
        "error": None,
    })
    resp = templates.TemplateResponse("acervo/programacao_form.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/new")
async def evento_new_save(
    request: Request,
    titulo: str       = Form(...),
    data_inicio: str  = Form(...),
    data_fim: str     = Form(""),
    local: str        = Form(""),
    maestro_id: str   = Form(""),
    descricao: str    = Form(""),
    publico: str      = Form("on"),
    db: Session       = Depends(get_db),
    current_user      = Depends(require_manage_acervo),
):
    try:
        dt_inicio = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc)
    except ValueError:
        ctx = make_ctx(request, {
            "evento": None, "maestros": _membros_maestros(db),
            "error": "Data de início inválida.",
        })
        return templates.TemplateResponse("acervo/programacao_form.html", ctx, status_code=422)

    dt_fim = None
    if data_fim:
        try:
            dt_fim = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    evento = Concerto(
        titulo      = titulo.strip(),
        data_inicio = dt_inicio,
        data_fim    = dt_fim,
        local       = local.strip() or None,
        maestro_id  = _parse_int(maestro_id),
        descricao   = descricao.strip() or None,
        publico     = publico == "on",
        created_by  = current_user["id"],
    )
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return RedirectResponse(url=f"/acervo/programacao/{evento.id}", status_code=303)


def _base_url(request: Request) -> str:
    return os.getenv("APP_BASE_URL", str(request.base_url).rstrip("/"))


@router.get("/{evento_id}", response_class=HTMLResponse)
def evento_detail(request: Request, evento_id: int, db: Session = Depends(get_db)):
    evento = db.query(Concerto).filter(Concerto.id == evento_id).first()
    if not evento:
        raise HTTPException(404)
    ids_no_programa = {ca.arranjo_id for ca in evento.programa}
    arranjos_disponiveis = (
        db.query(Arranjo)
        .filter(Arranjo.ativo == True)
        .filter(Arranjo.id.notin_(ids_no_programa) if ids_no_programa else True)
        .order_by(Arranjo.id)
        .all()
    )
    sugestoes = sugerir_distribuicao(db, evento) if evento.programa else []
    ctx = make_ctx(request, {
        "evento": evento,
        "arranjos_disponiveis": arranjos_disponiveis,
        "sugestoes_distribuicao": sugestoes,
        "base_url": _base_url(request),
    })
    resp = templates.TemplateResponse("acervo/programacao_detail.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.get("/{evento_id}/edit", response_class=HTMLResponse)
def evento_edit_form(
    request: Request,
    evento_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_manage_acervo),
):
    evento = db.query(Concerto).filter(Concerto.id == evento_id).first()
    if not evento:
        raise HTTPException(404)
    ctx = make_ctx(request, {
        "evento": evento,
        "maestros": _membros_maestros(db),
        "error": None,
    })
    resp = templates.TemplateResponse("acervo/programacao_form.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/{evento_id}/edit")
async def evento_edit_save(
    request: Request,
    evento_id: int,
    titulo: str       = Form(...),
    data_inicio: str  = Form(...),
    data_fim: str     = Form(""),
    local: str        = Form(""),
    maestro_id: str   = Form(""),
    descricao: str    = Form(""),
    publico: str      = Form("on"),
    db: Session       = Depends(get_db),
    current_user      = Depends(require_manage_acervo),
):
    evento = db.query(Concerto).filter(Concerto.id == evento_id).first()
    if not evento:
        raise HTTPException(404)
    try:
        evento.data_inicio = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc)
    except ValueError:
        ctx = make_ctx(request, {
            "evento": evento, "maestros": _membros_maestros(db),
            "error": "Data de início inválida.",
        })
        return templates.TemplateResponse("acervo/programacao_form.html", ctx, status_code=422)

    evento.titulo     = titulo.strip()
    evento.data_fim   = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc) if data_fim else None
    evento.local      = local.strip() or None
    evento.maestro_id = _parse_int(maestro_id)
    evento.descricao  = descricao.strip() or None
    evento.publico    = publico == "on"
    db.commit()
    return RedirectResponse(url=f"/acervo/programacao/{evento_id}", status_code=303)


@router.post("/{evento_id}/delete")
def evento_delete(
    request: Request,
    evento_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_manage_acervo),
):
    evento = db.query(Concerto).filter(Concerto.id == evento_id).first()
    if not evento:
        raise HTTPException(404)
    db.delete(evento)
    db.commit()
    return RedirectResponse(url="/acervo/programacao/calendario", status_code=303)


# ── Programa do Evento ─────────────────────────────────────────

@router.post("/{evento_id}/programa/add")
def programa_add(
    request: Request,
    evento_id: int,
    arranjo_id: str = Form(...),
    ordem: str      = Form(""),
    db: Session     = Depends(get_db),
    _user           = Depends(require_manage_acervo),
):
    evento = db.query(Concerto).filter(Concerto.id == evento_id).first()
    if not evento:
        raise HTTPException(404)
    aid = _parse_int(arranjo_id)
    if not aid:
        raise HTTPException(422)
    existing = db.query(ConcertoArranjo).filter_by(concerto_id=evento_id, arranjo_id=aid).first()
    if not existing:
        db.add(ConcertoArranjo(concerto_id=evento_id, arranjo_id=aid, ordem=_parse_int(ordem)))
        db.commit()
    return RedirectResponse(url=f"/acervo/programacao/{evento_id}", status_code=303)


@router.post("/{evento_id}/programa/{ca_id}/remove")
def programa_remove(
    request: Request,
    evento_id: int,
    ca_id: int,
    db: Session = Depends(get_db),
    _user       = Depends(require_manage_acervo),
):
    ca = db.query(ConcertoArranjo).filter_by(id=ca_id, concerto_id=evento_id).first()
    if ca:
        if ca.data_execucao:
            raise HTTPException(409, "Execução já registrada — não é possível remover.")
        db.delete(ca)
        db.commit()
    return RedirectResponse(url=f"/acervo/programacao/{evento_id}", status_code=303)


@router.post("/{evento_id}/programa/{ca_id}/execucao")
def programa_execucao(
    request: Request,
    evento_id: int,
    ca_id: int,
    data_execucao: str  = Form(...),
    duracao_real_m: str = Form(""),
    duracao_real_s: str = Form(""),
    observacoes: str    = Form(""),
    db: Session         = Depends(get_db),
    _user               = Depends(require_manage_acervo),
):
    ca = db.query(ConcertoArranjo).filter_by(id=ca_id, concerto_id=evento_id).first()
    if not ca:
        raise HTTPException(404)
    try:
        ca.data_execucao = datetime.fromisoformat(data_execucao).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(422, "Data inválida")
    m = _parse_int(duracao_real_m) or 0
    s = _parse_int(duracao_real_s) or 0
    ca.duracao_real_s = (m * 60 + s) if (m or s) else None
    ca.observacoes    = observacoes.strip() or None
    db.commit()
    return RedirectResponse(url=f"/acervo/programacao/{evento_id}", status_code=303)


# ── Distribuição de Partituras ─────────────────────────────────

@router.get("/{evento_id}/distribuir", response_class=HTMLResponse)
def distribuir_form(
    request: Request,
    evento_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_manage_acervo),
):
    evento = db.query(Concerto).filter(Concerto.id == evento_id).first()
    if not evento:
        raise HTTPException(404)
    if not evento.programa:
        raise HTTPException(422, "Adicione obras ao programa antes de distribuir partituras.")

    from app.routers.whatsapp_pwa import list_grupos_com_telefone

    sugestoes = sugerir_distribuicao(db, evento)
    acessos_existentes = {
        a.musician_id: a for a in (evento.acessos_partituras or [])
    }
    wa_telefones = list_grupos_com_telefone(db)
    ctx = make_ctx(request, {
        "evento": evento,
        "sugestoes": sugestoes,
        "acessos_existentes": acessos_existentes,
        "base_url": _base_url(request),
        "wa_telefones_count": len(wa_telefones),
        "wa_telefones": wa_telefones,
    })
    resp = templates.TemplateResponse("acervo/distribuir_partituras.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/{evento_id}/distribuir")
async def distribuir_salvar(
    request: Request,
    evento_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_manage_acervo),
):
    evento = db.query(Concerto).filter(Concerto.id == evento_id).first()
    if not evento:
        raise HTTPException(404)

    form = await request.form()
    atribuicoes = []
    musician_ids = set()
    for key in form.keys():
        if key.startswith("doc_"):
            parts = key.split("_")
            if len(parts) >= 3:
                musician_ids.add(int(parts[1]))

    for mid in musician_ids:
        doc_ids = []
        for key, val in form.items():
            if key.startswith(f"doc_{mid}_") and val == "on":
                doc_id = int(key.split("_")[-1])
                doc_ids.append(doc_id)
        if doc_ids:
            atribuicoes.append({"musician_id": mid, "documento_ids": doc_ids})

    enviar_email = form.get("enviar_email") == "on"
    enviar_whatsapp = form.get("enviar_whatsapp") == "on"
    acessos = criar_ou_atualizar_acessos(db, evento, atribuicoes)
    db.commit()

    base = _base_url(request)
    smtp = getattr(request.app.state, "smtp_settings", {})
    data_fmt = evento.data_inicio.strftime("%d/%m/%Y %H:%M")

    if enviar_email:
        for acesso in acessos:
            m = acesso.musician
            if m.email:
                url = f"{base}/acervo/programacao/acesso/{acesso.token}"
                send_partituras_evento(
                    m.email, m.full_name, evento.titulo, data_fmt, url, smtp
                )
                acesso.enviado_em = datetime.now(timezone.utc)
        db.commit()

    if enviar_whatsapp:
        return RedirectResponse(
            url=f"/acervo/programacao/{evento_id}/whatsapp?auto=1",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/acervo/programacao/{evento_id}?distribuido=1",
        status_code=303,
    )


@router.get("/{evento_id}/whatsapp", response_class=HTMLResponse)
def distribuir_whatsapp(
    request: Request,
    evento_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_manage_acervo),
):
    """Abre WhatsApp com link PWA para cada telefone cadastrado nos naipes."""
    from app.routers.whatsapp_pwa import build_evento_wa_payloads, pwa_url_from_request

    evento = db.query(Concerto).filter(Concerto.id == evento_id).first()
    if not evento:
        raise HTTPException(404)

    data_fmt = evento.data_inicio.strftime("%d/%m/%Y %H:%M")
    envios = build_evento_wa_payloads(
        db,
        request,
        evento_titulo=evento.titulo,
        data_fmt=data_fmt,
        local=evento.local,
    )
    auto_open = (request.query_params.get("auto") or "") in {"1", "true", "yes"}
    ctx = make_ctx(request, {
        "evento": evento,
        "envios": envios,
        "pwa_url": pwa_url_from_request(request),
        "auto_open": auto_open,
    })
    resp = templates.TemplateResponse("acervo/whatsapp_envio.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


def _tz_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("/acesso/{token}", response_class=HTMLResponse)
def acesso_partituras_publico(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
):
    """Página pública para músico acessar partituras do evento (sem login)."""
    import uuid as uuid_lib
    try:
        token_uuid = uuid_lib.UUID(str(token))
    except ValueError:
        raise HTTPException(404, "Link inválido")

    acesso = (
        db.query(ConcertoAcessoPartitura)
        .filter(ConcertoAcessoPartitura.token == token_uuid)
        .first()
    )
    if not acesso:
        raise HTTPException(404, "Link não encontrado")

    agora = datetime.now(timezone.utc)
    exp = _tz_aware(acesso.expires_at)
    valid_from = _tz_aware(acesso.valid_from)

    if agora > exp:
        ctx = make_ctx(request, {
            "expirado": True,
            "ainda_nao_disponivel": False,
            "evento": acesso.concerto,
            "valid_from": valid_from,
        })
        return templates.TemplateResponse("acervo/partituras_evento.html", ctx)

    if valid_from and agora < valid_from:
        ctx = make_ctx(request, {
            "expirado": False,
            "ainda_nao_disponivel": True,
            "evento": acesso.concerto,
            "musician": acesso.musician,
            "valid_from": valid_from,
            "token": token,
        })
        return templates.TemplateResponse("acervo/partituras_evento.html", ctx)

    documentos = (
        db.query(ArranjoDocumento)
        .filter(ArranjoDocumento.id.in_(acesso.documento_ids or []))
        .all()
    )

    ctx = make_ctx(request, {
        "acesso": acesso,
        "evento": acesso.concerto,
        "musician": acesso.musician,
        "documentos": documentos,
        "token": token,
        "expirado": False,
        "ainda_nao_disponivel": False,
        "valid_from": valid_from,
    })
    resp = templates.TemplateResponse("acervo/partituras_evento.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.get("/acesso/{token}/download/{documento_id}")
def acesso_download(
    token: str,
    documento_id: int,
    db: Session = Depends(get_db),
):
    """Download seguro via token de acesso do evento."""
    import uuid as uuid_lib
    try:
        token_uuid = uuid_lib.UUID(str(token))
    except ValueError:
        raise HTTPException(403, "Link inválido")

    acesso = (
        db.query(ConcertoAcessoPartitura)
        .filter(ConcertoAcessoPartitura.token == token_uuid)
        .first()
    )
    if not acesso:
        raise HTTPException(403, "Acesso negado")

    agora = datetime.now(timezone.utc)
    exp = _tz_aware(acesso.expires_at)
    valid_from = _tz_aware(acesso.valid_from)

    if agora > exp:
        raise HTTPException(403, "Link expirado")
    if valid_from and agora < valid_from:
        raise HTTPException(403, "Partituras disponíveis a partir do dia do evento")

    if documento_id not in (acesso.documento_ids or []):
        raise HTTPException(403, "Documento não autorizado")

    doc = db.query(ArranjoDocumento).filter_by(id=documento_id).first()
    if not doc:
        raise HTTPException(404, "Documento não encontrado")

    path = Path("uploads") / doc.arquivo_caminho
    if not path.exists():
        raise HTTPException(404, "Arquivo não encontrado")

    return FileResponse(path, filename=path.name)


# ── iCal público ─────────────────────────────────────────────
# (também disponível em /acervo/calendario.ics via acervo.py,
#  mantemos aqui como alternativa para o router de programação)

@router.get("/ical/feed.ics")
def ical_feed(db: Session = Depends(get_db)):
    from icalendar import Calendar, Event as ICalEvent
    eventos = db.execute(text("""
        SELECT c.id, c.titulo, c.data_inicio, c.data_fim,
               c.local, c.descricao, c.cal_uid,
               m.first_name || ' ' || m.last_name AS maestro_nome
        FROM concertos c
        LEFT JOIN musicians m ON m.id = c.maestro_id
        WHERE c.publico = TRUE
        ORDER BY c.data_inicio
    """)).fetchall()

    cal = Calendar()
    cal.add("PRODID", "-//Orchestra Portal//Programacao Musical//PT")
    cal.add("VERSION", "2.0")
    cal.add("CALSCALE", "GREGORIAN")
    cal.add("X-WR-CALNAME", "Programação Musical")
    cal.add("X-WR-TIMEZONE", "America/Sao_Paulo")

    for e in eventos:
        ev = ICalEvent()
        ev.add("UID",     str(e.cal_uid))
        ev.add("SUMMARY", e.titulo)
        dt_start = e.data_inicio
        if dt_start and dt_start.tzinfo is None:
            dt_start = dt_start.replace(tzinfo=timezone.utc)
        dt_end = e.data_fim or e.data_inicio
        if dt_end and dt_end.tzinfo is None:
            dt_end = dt_end.replace(tzinfo=timezone.utc)
        ev.add("DTSTART", dt_start)
        ev.add("DTEND",   dt_end)
        if e.local:
            ev.add("LOCATION", e.local)
        desc_parts = []
        if e.descricao:
            desc_parts.append(e.descricao)
        if e.maestro_nome:
            desc_parts.append(f"Maestro(a): {e.maestro_nome}")
        if desc_parts:
            ev.add("DESCRIPTION", "\n".join(desc_parts))
        cal.add_component(ev)

    return Response(
        content=cal.to_ical(),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=programacao.ics"},
    )


# ══════════════════════════════════════════════════════════════
# Compat: /acervo/concertos → /acervo/programacao
# (atalhos e templates legados ainda usam "Concertos")
# ══════════════════════════════════════════════════════════════

compat_router = APIRouter(prefix="/acervo/concertos", tags=["Concertos Compat"])


@compat_router.get("")
@compat_router.get("/")
def concertos_list_redirect():
    return RedirectResponse(url="/acervo/programacao/lista", status_code=302)


@compat_router.get("/new")
def concertos_new_form_redirect():
    return RedirectResponse(url="/acervo/programacao/new", status_code=302)


@compat_router.api_route("/new", methods=["POST"])
def concertos_new_post_redirect():
    return RedirectResponse(url="/acervo/programacao/new", status_code=307)


@compat_router.get("/{evento_id}/edit")
def concertos_edit_form_redirect(evento_id: int):
    return RedirectResponse(url=f"/acervo/programacao/{evento_id}/edit", status_code=302)


@compat_router.api_route("/{evento_id}/edit", methods=["POST"])
def concertos_edit_post_redirect(evento_id: int):
    return RedirectResponse(url=f"/acervo/programacao/{evento_id}/edit", status_code=307)


@compat_router.api_route("/{evento_id}/delete", methods=["POST"])
def concertos_delete_redirect(evento_id: int):
    return RedirectResponse(url=f"/acervo/programacao/{evento_id}/delete", status_code=307)


@compat_router.api_route("/{evento_id}/programa/add", methods=["POST"])
def concertos_programa_add_redirect(evento_id: int):
    return RedirectResponse(url=f"/acervo/programacao/{evento_id}/programa/add", status_code=307)


@compat_router.api_route("/{evento_id}/programa/{ca_id}/remove", methods=["POST"])
def concertos_programa_remove_redirect(evento_id: int, ca_id: int):
    return RedirectResponse(
        url=f"/acervo/programacao/{evento_id}/programa/{ca_id}/remove",
        status_code=307,
    )


@compat_router.api_route("/{evento_id}/programa/{ca_id}/execucao", methods=["POST"])
def concertos_programa_exec_redirect(evento_id: int, ca_id: int):
    return RedirectResponse(
        url=f"/acervo/programacao/{evento_id}/programa/{ca_id}/execucao",
        status_code=307,
    )


@compat_router.get("/{evento_id}")
def concertos_detail_redirect(evento_id: int):
    return RedirectResponse(url=f"/acervo/programacao/{evento_id}", status_code=302)
