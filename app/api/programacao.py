"""API v1 — programação / concertos (admin)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_api_manage_acervo, require_system_user
from app.eventos_query import EVENTOS_SQL, eventos_params
from app.database import get_db
from app.distribuicao import criar_ou_atualizar_acessos, sugerir_distribuicao
from app.models import Arranjo, Concerto, ConcertoArranjo, User

router = APIRouter(prefix="/programacao", tags=["Programacao"])


def _doc_brief(d) -> dict:
    return {
        "id": d.id,
        "tipo": d.tipo,
        "tipo_label": getattr(d, "tipo_label", d.tipo),
        "instrumento_nome": d.instrumento_nome,
        "voz_tipo": d.voz_tipo,
        "arquivo_caminho": d.arquivo_caminho,
        "tamanho_bytes": d.tamanho_bytes,
    }


def _ser(c: Concerto) -> dict:
    programa = []
    for ca in c.programa or []:
        arranjo = ca.arranjo
        titulo = None
        documentos = []
        if arranjo:
            titulo = arranjo.titulo_arranjo or (arranjo.obra.titulo if arranjo.obra else None)
            documentos = [_doc_brief(d) for d in (arranjo.documentos or [])]
        programa.append(
            {
                "id": ca.id,
                "arranjo_id": ca.arranjo_id,
                "ordem": ca.ordem,
                "titulo": titulo,
                "data_execucao": ca.data_execucao.isoformat() if ca.data_execucao else None,
                "duracao_real_s": ca.duracao_real_s,
                "observacoes": ca.observacoes,
                "documentos": documentos,
            }
        )
    return {
        "id": c.id,
        "titulo": c.titulo,
        "data_inicio": c.data_inicio.isoformat() if c.data_inicio else None,
        "data_fim": c.data_fim.isoformat() if c.data_fim else None,
        "local": c.local,
        "maestro_id": c.maestro_id,
        "maestro_nome": c.maestro.full_name if c.maestro else None,
        "descricao": c.descricao,
        "publico": c.publico,
        "programa": programa,
    }


def _base_url(request: Request) -> str:
    return os.getenv("APP_BASE_URL") or str(request.base_url).rstrip("/")


def _serialize_sugestoes(sugestoes: list) -> list:
    out = []
    for s in sugestoes:
        m = s["musician"]
        out.append(
            {
                "musician_id": m.id,
                "musician_name": m.full_name,
                "musician_email": m.email,
                "obras": s.get("obras") or [],
                "documento_ids": [d.id for d in s.get("documentos") or []],
                "documentos": [_doc_brief(d) for d in s.get("documentos") or []],
            }
        )
    return out


def _serialize_acessos(evento: Concerto) -> list:
    return [
        {
            "id": a.id,
            "musician_id": a.musician_id,
            "musician_name": a.musician.full_name if a.musician else None,
            "musician_email": a.musician.email if a.musician else None,
            "documento_ids": a.documento_ids or [],
            "token": str(a.token),
            "valid_from": a.valid_from.isoformat() if a.valid_from else None,
            "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            "enviado_em": a.enviado_em.isoformat() if a.enviado_em else None,
        }
        for a in (evento.acessos_partituras or [])
    ]


class ConcertoIn(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=300)
    data_inicio: datetime
    data_fim: Optional[datetime] = None
    local: Optional[str] = None
    maestro_id: Optional[int] = None
    descricao: Optional[str] = None
    publico: bool = True


class ProgramaAdd(BaseModel):
    arranjo_id: int
    ordem: Optional[int] = None


class ExecucaoBody(BaseModel):
    data_execucao: datetime
    duracao_real_s: Optional[int] = None
    observacoes: Optional[str] = None


class AtribuicaoItem(BaseModel):
    musician_id: int
    documento_ids: list[int] = Field(default_factory=list)


class DistribuirBody(BaseModel):
    atribuicoes: list[AtribuicaoItem] = Field(default_factory=list)
    enviar_email: bool = False


@router.get("/eventos")
async def eventos_json(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    """FullCalendar-compatible events JSON (ported from Jinja eventos_json)."""
    query_params = eventos_params(start, end)
    rows = db.execute(EVENTOS_SQL, query_params).fetchall()

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

        events.append(
            {
                "id": str(r.id),
                "title": r.titulo,
                "start": dt_start.isoformat() if dt_start else None,
                "end": dt_end.isoformat() if dt_end else None,
                "url": f"/acervo/programacao/{r.id}",
                "backgroundColor": "#4f6ef7" if r.publico else "#94a3b8",
                "borderColor": "#3b5bdb" if r.publico else "#64748b",
                "extendedProps": {
                    "local": r.local or "",
                    "maestro": r.maestro_nome or "",
                    "num_obras": r.num_obras or 0,
                    "descricao": "\n".join(desc_parts),
                },
            }
        )
    return events


@router.get("/concertos")
async def list_concertos(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    q = db.query(Concerto)
    total = q.count()
    items = q.order_by(Concerto.data_inicio.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": [_ser(c) for c in items]}


@router.get("/concertos/{concerto_id}")
async def get_concerto(concerto_id: int, db: Session = Depends(get_db), _: User = Depends(require_system_user)):
    c = db.query(Concerto).filter(Concerto.id == concerto_id).first()
    if not c:
        raise HTTPException(404, "Concerto não encontrado.")
    return _ser(c)


@router.post("/concertos", status_code=201)
async def create_concerto(body: ConcertoIn, db: Session = Depends(get_db), user: User = Depends(require_api_manage_acervo)):
    c = Concerto(
        titulo=body.titulo.strip(),
        data_inicio=body.data_inicio,
        data_fim=body.data_fim,
        local=(body.local or "").strip() or None,
        maestro_id=body.maestro_id,
        descricao=(body.descricao or "").strip() or None,
        publico=body.publico,
        created_by=user.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _ser(c)


@router.put("/concertos/{concerto_id}")
async def update_concerto(
    concerto_id: int,
    body: ConcertoIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_acervo),
):
    c = db.query(Concerto).filter(Concerto.id == concerto_id).first()
    if not c:
        raise HTTPException(404, "Concerto não encontrado.")
    c.titulo = body.titulo.strip()
    c.data_inicio = body.data_inicio
    c.data_fim = body.data_fim
    c.local = (body.local or "").strip() or None
    c.maestro_id = body.maestro_id
    c.descricao = (body.descricao or "").strip() or None
    c.publico = body.publico
    db.commit()
    db.refresh(c)
    return _ser(c)


@router.delete("/concertos/{concerto_id}")
async def delete_concerto(concerto_id: int, db: Session = Depends(get_db), _: User = Depends(require_api_manage_acervo)):
    c = db.query(Concerto).filter(Concerto.id == concerto_id).first()
    if not c:
        raise HTTPException(404, "Concerto não encontrado.")
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.post("/concertos/{concerto_id}/programa")
async def add_programa(
    concerto_id: int,
    body: ProgramaAdd,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_acervo),
):
    c = db.query(Concerto).filter(Concerto.id == concerto_id).first()
    if not c:
        raise HTTPException(404, "Concerto não encontrado.")
    if not db.query(Arranjo).filter(Arranjo.id == body.arranjo_id).first():
        raise HTTPException(404, "Arranjo não encontrado.")
    ordem = body.ordem
    if ordem is None:
        ordem = len(c.programa or []) + 1
    ca = ConcertoArranjo(concerto_id=c.id, arranjo_id=body.arranjo_id, ordem=ordem)
    db.add(ca)
    db.commit()
    db.refresh(c)
    return _ser(c)


@router.delete("/concertos/{concerto_id}/programa/{item_id}")
async def remove_programa(
    concerto_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_acervo),
):
    ca = (
        db.query(ConcertoArranjo)
        .filter(ConcertoArranjo.id == item_id, ConcertoArranjo.concerto_id == concerto_id)
        .first()
    )
    if not ca:
        raise HTTPException(404, "Item não encontrado.")
    if ca.data_execucao:
        raise HTTPException(409, "Execução já registrada — não é possível remover.")
    db.delete(ca)
    db.commit()
    c = db.query(Concerto).filter(Concerto.id == concerto_id).first()
    return _ser(c)


@router.post("/concertos/{concerto_id}/programa/{item_id}/execucao")
async def registrar_execucao(
    concerto_id: int,
    item_id: int,
    body: ExecucaoBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_acervo),
):
    ca = (
        db.query(ConcertoArranjo)
        .filter(ConcertoArranjo.id == item_id, ConcertoArranjo.concerto_id == concerto_id)
        .first()
    )
    if not ca:
        raise HTTPException(404, "Item não encontrado.")
    ca.data_execucao = body.data_execucao
    ca.duracao_real_s = body.duracao_real_s
    ca.observacoes = (body.observacoes or "").strip() or None
    db.commit()
    c = db.query(Concerto).filter(Concerto.id == concerto_id).first()
    return _ser(c)


@router.get("/concertos/{concerto_id}/distribuicao")
async def get_distribuicao(
    concerto_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_acervo),
):
    c = db.query(Concerto).filter(Concerto.id == concerto_id).first()
    if not c:
        raise HTTPException(404, "Concerto não encontrado.")
    sugestoes = sugerir_distribuicao(db, c) if c.programa else []
    return {
        "concerto_id": c.id,
        "sugestoes": _serialize_sugestoes(sugestoes),
        "acessos": _serialize_acessos(c),
    }


@router.post("/concertos/{concerto_id}/distribuir")
async def distribuir(
    concerto_id: int,
    request: Request,
    body: DistribuirBody = DistribuirBody(),
    db: Session = Depends(get_db),
    user: User = Depends(require_api_manage_acervo),
):
    """Cria/atualiza acessos de partituras do evento."""
    from app.email_utils import send_partituras_evento

    c = db.query(Concerto).filter(Concerto.id == concerto_id).first()
    if not c:
        raise HTTPException(404, "Concerto não encontrado.")

    enviar_email = bool(body.enviar_email)
    if body.atribuicoes:
        atribuicoes = [{"musician_id": a.musician_id, "documento_ids": a.documento_ids} for a in body.atribuicoes]
    else:
        sugestoes = sugerir_distribuicao(db, c)
        atribuicoes = [
            {"musician_id": s["musician"].id, "documento_ids": [d.id for d in s["documentos"]]}
            for s in sugestoes
            if s.get("documentos")
        ]

    try:
        acessos = criar_ou_atualizar_acessos(db, c, atribuicoes)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    db.commit()

    emails_enviados = 0
    if enviar_email:
        base = _base_url(request)
        smtp = getattr(request.app.state, "smtp_settings", None) or {}
        if not smtp:
            try:
                from app.routers.settings import _read_smtp

                smtp = _read_smtp()
            except Exception:
                smtp = {}
        data_fmt = c.data_inicio.strftime("%d/%m/%Y %H:%M") if c.data_inicio else ""
        for acesso in acessos:
            m = acesso.musician
            if m and m.email:
                url = f"{base}/acervo/programacao/acesso/{acesso.token}"
                try:
                    send_partituras_evento(m.email, m.full_name, c.titulo, data_fmt, url, smtp)
                    acesso.enviado_em = datetime.now(timezone.utc)
                    emails_enviados += 1
                except Exception:
                    pass
        db.commit()

    return {
        "ok": True,
        "atribuicoes": len(atribuicoes),
        "acessos": _serialize_acessos(c),
        "emails_enviados": emails_enviados,
        "actor_user_id": getattr(user, "id", None),
    }
