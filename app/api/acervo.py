"""API v1 — acervo (obras, arranjos) e programação (concertos)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.acervo_storage import salvar_upload
from app.api.deps import require_api_manage_acervo, require_system_user
from app.database import get_db
from app.models import (
    Arranjo,
    ArranjoDocumento,
    Concerto,
    ConcertoArranjo,
    CopyrightStatus,
    GeneroMusical,
    Obra,
    User,
)

router = APIRouter(prefix="/acervo", tags=["Acervo"])


def _doc_ser(d: ArranjoDocumento) -> dict:
    return {
        "id": d.id,
        "arranjo_id": d.arranjo_id,
        "tipo": d.tipo,
        "tipo_label": d.tipo_label,
        "instrumento_nome": d.instrumento_nome,
        "voz_tipo": d.voz_tipo,
        "arquivo_caminho": d.arquivo_caminho,
        "tamanho_bytes": d.tamanho_bytes,
    }


def _obra_ser(o: Obra) -> dict:
    return {
        "id": o.id,
        "titulo": o.titulo,
        "titulo_original": o.titulo_original,
        "compositor_id": o.compositor_id,
        "compositor_nome": o.compositor_nome,
        "compositor_label": o.compositor_label,
        "genero": o.genero.value if hasattr(o.genero, "value") else str(o.genero),
        "tonalidade": o.tonalidade,
        "ano_composicao": o.ano_composicao,
        "observacoes": o.observacoes,
        "arranjos_count": len(o.arranjos or []),
    }


def _arranjo_ser(a: Arranjo, *, include_docs: bool = False) -> dict:
    data = {
        "id": a.id,
        "obra_id": a.obra_id,
        "obra_titulo": a.obra.titulo if a.obra else None,
        "titulo_arranjo": a.titulo_arranjo,
        "arranjador_id": a.arranjador_id,
        "arranjador_nome": a.arranjador_nome,
        "arranjador_label": a.arranjador_label,
        "instrumentacao": a.instrumentacao,
        "duracao_segundos": a.duracao_segundos,
        "duracao_label": a.duracao_label,
        "editora": a.editora,
        "copyright_status": a.copyright_status.value if hasattr(a.copyright_status, "value") else str(a.copyright_status),
        "numero_licenca": a.numero_licenca,
        "ativo": a.ativo,
    }
    if include_docs:
        data["documentos"] = [_doc_ser(d) for d in (a.documentos or [])]
    return data


def _concerto_ser(c: Concerto) -> dict:
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
    }


def _documento_path(doc: ArranjoDocumento) -> Path:
    return Path("uploads") / doc.arquivo_caminho


def _indexar_documento_best_effort(db: Session, documento: ArranjoDocumento, arranjo: Arranjo) -> None:
    try:
        from app.search_index import DocumentoSearchIndex

        obra = arranjo.obra
        search_index = DocumentoSearchIndex()
        search_index.indexar(
            documento_id=documento.id,
            arranjo_id=arranjo.id,
            titulo_obra=obra.titulo if obra else (arranjo.titulo_arranjo or ""),
            compositor=obra.compositor_label if obra else "",
            tipo_documento=documento.tipo,
            instrumento=documento.instrumento_nome or documento.voz_tipo or "",
            caminho_arquivo=documento.arquivo_caminho,
        )
        search_index.close()
    except Exception:
        pass


class ObraCreate(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=300)
    titulo_original: Optional[str] = None
    compositor_id: Optional[int] = None
    compositor_nome: Optional[str] = None
    genero: str = "outro"
    tonalidade: Optional[str] = None
    ano_composicao: Optional[int] = None
    observacoes: Optional[str] = None


class ObraUpdate(ObraCreate):
    titulo: Optional[str] = Field(None, min_length=1, max_length=300)
    genero: Optional[str] = None


class ArranjoCreate(BaseModel):
    obra_id: Optional[int] = None
    titulo_arranjo: Optional[str] = None
    arranjador_id: Optional[int] = None
    arranjador_nome: Optional[str] = None
    instrumentacao: str = Field(..., min_length=1)
    duracao_segundos: Optional[int] = None
    editora: Optional[str] = None
    copyright_status: str = "pendente"
    numero_licenca: Optional[str] = None
    ativo: bool = True


class ArranjoUpdate(BaseModel):
    obra_id: Optional[int] = None
    titulo_arranjo: Optional[str] = None
    arranjador_id: Optional[int] = None
    arranjador_nome: Optional[str] = None
    instrumentacao: Optional[str] = Field(None, min_length=1)
    duracao_segundos: Optional[int] = None
    editora: Optional[str] = None
    copyright_status: Optional[str] = None
    numero_licenca: Optional[str] = None
    ativo: Optional[bool] = None


class ConcertoCreate(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=300)
    data_inicio: datetime
    data_fim: Optional[datetime] = None
    local: Optional[str] = None
    maestro_id: Optional[int] = None
    descricao: Optional[str] = None
    publico: bool = True


# ── Obras ────────────────────────────────────────────────────

@router.get("/obras")
async def list_obras(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    query = db.query(Obra)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(Obra.titulo.ilike(term), Obra.titulo_original.ilike(term), Obra.compositor_nome.ilike(term))
        )
    total = query.count()
    items = query.order_by(Obra.titulo).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_obra_ser(o) for o in items]}


@router.get("/obras/{obra_id}")
async def get_obra(obra_id: int, db: Session = Depends(get_db), _: User = Depends(require_system_user)):
    o = db.query(Obra).filter(Obra.id == obra_id).first()
    if not o:
        raise HTTPException(404, "Obra não encontrada.")
    data = _obra_ser(o)
    data["arranjos"] = [_arranjo_ser(a, include_docs=True) for a in (o.arranjos or [])]
    return data


@router.post("/obras", status_code=201)
async def create_obra(body: ObraCreate, db: Session = Depends(get_db), user: User = Depends(require_api_manage_acervo)):
    try:
        genero = GeneroMusical(body.genero)
    except ValueError:
        genero = GeneroMusical.outro
    o = Obra(
        titulo=body.titulo.strip(),
        titulo_original=(body.titulo_original or "").strip() or None,
        compositor_id=body.compositor_id,
        compositor_nome=(body.compositor_nome or "").strip() or None,
        genero=genero,
        tonalidade=(body.tonalidade or "").strip() or None,
        ano_composicao=body.ano_composicao,
        observacoes=(body.observacoes or "").strip() or None,
        created_by=user.id,
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return _obra_ser(o)


@router.put("/obras/{obra_id}")
async def update_obra(
    obra_id: int,
    body: ObraUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_acervo),
):
    o = db.query(Obra).filter(Obra.id == obra_id).first()
    if not o:
        raise HTTPException(404, "Obra não encontrada.")
    data = body.model_dump(exclude_unset=True)
    if "genero" in data and data["genero"]:
        try:
            o.genero = GeneroMusical(data.pop("genero"))
        except ValueError:
            data.pop("genero", None)
    for k, v in data.items():
        setattr(o, k, v)
    db.commit()
    db.refresh(o)
    return _obra_ser(o)


@router.delete("/obras/{obra_id}")
async def delete_obra(obra_id: int, db: Session = Depends(get_db), _: User = Depends(require_api_manage_acervo)):
    o = db.query(Obra).filter(Obra.id == obra_id).first()
    if not o:
        raise HTTPException(404, "Obra não encontrada.")
    db.delete(o)
    db.commit()
    return {"ok": True}


# ── Busca / Histórico (antes de rotas com path params ambíguos) ─

@router.get("/busca")
async def busca_acervo(
    q: str = "",
    compositor: str = "",
    arranjador: str = "",
    instrumento: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    if not (q or compositor or arranjador or instrumento):
        return {"obras": [], "arranjos": [], "items": []}

    rows = db.execute(
        text("""
            SELECT
                o.id              AS obra_id,
                o.titulo,
                COALESCE(mc.first_name || ' ' || mc.last_name, o.compositor_nome) AS compositor,
                o.genero,
                o.tonalidade,
                a.id              AS arranjo_id,
                COALESCE(a.titulo_arranjo, 'Arranjo principal') AS titulo_arranjo,
                COALESCE(ma.first_name || ' ' || ma.last_name, a.arranjador_nome, '—') AS arranjador,
                a.instrumentacao,
                a.duracao_segundos,
                a.copyright_status
            FROM arranjos a
            LEFT JOIN obras o     ON o.id = a.obra_id
            LEFT JOIN musicians mc ON mc.id = o.compositor_id
            LEFT JOIN musicians ma ON ma.id = a.arranjador_id
            WHERE a.ativo = TRUE
              AND (:q IS NULL OR (
                    COALESCE(o.titulo, '') ILIKE '%' || :q || '%'
                    OR a.instrumentacao ILIKE '%' || :q || '%'
                    OR COALESCE(mc.first_name || ' ' || mc.last_name, o.compositor_nome, '') ILIKE '%' || :q || '%'
                ))
              AND (:compositor IS NULL OR
                    COALESCE(mc.first_name || ' ' || mc.last_name, o.compositor_nome, '') ILIKE '%' || :compositor || '%')
              AND (:arranjador IS NULL OR
                    COALESCE(ma.first_name || ' ' || ma.last_name, a.arranjador_nome, '') ILIKE '%' || :arranjador || '%')
              AND (:instrumento IS NULL OR
                    a.instrumentacao ILIKE '%' || :instrumento || '%')
            ORDER BY COALESCE(o.titulo, 'ZZZ'), a.id
            LIMIT 100
        """),
        {
            "q": q.strip() or None,
            "compositor": compositor.strip() or None,
            "arranjador": arranjador.strip() or None,
            "instrumento": instrumento.strip() or None,
        },
    ).fetchall()

    items = [
        {
            "obra_id": r.obra_id,
            "titulo": r.titulo,
            "compositor": r.compositor,
            "genero": r.genero,
            "tonalidade": r.tonalidade,
            "arranjo_id": r.arranjo_id,
            "titulo_arranjo": r.titulo_arranjo,
            "arranjador": r.arranjador,
            "instrumentacao": r.instrumentacao,
            "duracao_segundos": r.duracao_segundos,
            "copyright_status": r.copyright_status,
        }
        for r in rows
    ]
    obras_map: dict = {}
    for it in items:
        oid = it["obra_id"]
        if oid and oid not in obras_map:
            obras_map[oid] = {
                "id": oid,
                "titulo": it["titulo"],
                "compositor": it["compositor"],
                "genero": it["genero"],
                "tonalidade": it["tonalidade"],
            }
    arranjos = [
        {
            "id": it["arranjo_id"],
            "obra_id": it["obra_id"],
            "titulo_arranjo": it["titulo_arranjo"],
            "arranjador": it["arranjador"],
            "instrumentacao": it["instrumentacao"],
            "duracao_segundos": it["duracao_segundos"],
            "copyright_status": it["copyright_status"],
            "obra_titulo": it["titulo"],
        }
        for it in items
    ]
    return {"obras": list(obras_map.values()), "arranjos": arranjos, "items": items}


@router.get("/historico")
async def historico_execucoes(
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
    limit: int = Query(100, ge=1, le=500),
):
    rows = (
        db.query(ConcertoArranjo)
        .filter(ConcertoArranjo.data_execucao.isnot(None))
        .order_by(ConcertoArranjo.data_execucao.desc())
        .limit(limit)
        .all()
    )
    execucoes = []
    for ca in rows:
        arranjo = ca.arranjo
        obra = arranjo.obra if arranjo else None
        concerto = ca.concerto
        execucoes.append(
            {
                "id": ca.id,
                "concerto_id": ca.concerto_id,
                "concerto_titulo": concerto.titulo if concerto else None,
                "arranjo_id": ca.arranjo_id,
                "titulo_arranjo": (arranjo.titulo_arranjo if arranjo else None)
                or (obra.titulo if obra else None),
                "obra_id": obra.id if obra else None,
                "obra_titulo": obra.titulo if obra else None,
                "data_execucao": ca.data_execucao.isoformat() if ca.data_execucao else None,
                "duracao_real_s": ca.duracao_real_s,
                "observacoes": ca.observacoes,
            }
        )

    top_mais = db.execute(
        text("""
            SELECT o.titulo, COUNT(ca.id) AS total
            FROM concerto_arranjos ca
            JOIN arranjos a ON a.id = ca.arranjo_id
            JOIN obras    o ON o.id = a.obra_id
            WHERE ca.data_execucao IS NOT NULL
            GROUP BY o.id, o.titulo
            ORDER BY total DESC LIMIT 10
        """)
    ).fetchall()

    return {
        "execucoes": execucoes,
        "top_mais": [{"titulo": r.titulo, "total": r.total} for r in top_mais],
    }


# ── Documentos ───────────────────────────────────────────────

@router.get("/documentos/{documento_id}/download")
async def download_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    doc = db.query(ArranjoDocumento).filter_by(id=documento_id).first()
    if not doc:
        raise HTTPException(404, "Documento não encontrado.")
    path = _documento_path(doc)
    if not path.exists():
        raise HTTPException(404, "Arquivo não encontrado no servidor.")
    return FileResponse(path, filename=path.name)


@router.get("/documentos/{documento_id}/view")
async def view_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    doc = db.query(ArranjoDocumento).filter_by(id=documento_id).first()
    if not doc:
        raise HTTPException(404, "Documento não encontrado.")
    path = _documento_path(doc)
    if not path.exists():
        raise HTTPException(404, "Arquivo não encontrado no servidor.")
    media = "application/pdf" if path.suffix.lower() == ".pdf" else "application/octet-stream"
    return FileResponse(
        path,
        media_type=media,
        filename=path.name,
        content_disposition_type="inline",
    )


@router.delete("/documentos/{documento_id}")
async def delete_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_acervo),
):
    doc = db.query(ArranjoDocumento).filter_by(id=documento_id).first()
    if not doc:
        raise HTTPException(404, "Documento não encontrado.")
    path = _documento_path(doc)
    arranjo = doc.arranjo
    if arranjo and arranjo.arquivo_partitura == doc.arquivo_caminho:
        arranjo.arquivo_partitura = None
    db.delete(doc)
    db.commit()
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
    return {"ok": True}


# ── Arranjos ─────────────────────────────────────────────────

@router.get("/arranjos")
async def list_arranjos(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    query = db.query(Arranjo)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(Arranjo.titulo_arranjo.ilike(term), Arranjo.arranjador_nome.ilike(term), Arranjo.instrumentacao.ilike(term))
        )
    total = query.count()
    items = query.order_by(Arranjo.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_arranjo_ser(a) for a in items]}


@router.get("/arranjos/{arranjo_id}")
async def get_arranjo(
    arranjo_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    a = db.query(Arranjo).filter(Arranjo.id == arranjo_id).first()
    if not a:
        raise HTTPException(404, "Arranjo não encontrado.")
    return _arranjo_ser(a, include_docs=True)


@router.post("/arranjos", status_code=201)
async def create_arranjo(body: ArranjoCreate, db: Session = Depends(get_db), user: User = Depends(require_api_manage_acervo)):
    try:
        cs = CopyrightStatus(body.copyright_status)
    except ValueError:
        cs = CopyrightStatus.pendente
    a = Arranjo(
        obra_id=body.obra_id,
        titulo_arranjo=(body.titulo_arranjo or "").strip() or None,
        arranjador_id=body.arranjador_id,
        arranjador_nome=(body.arranjador_nome or "").strip() or None,
        instrumentacao=body.instrumentacao.strip(),
        duracao_segundos=body.duracao_segundos,
        editora=(body.editora or "").strip() or None,
        copyright_status=cs,
        numero_licenca=(body.numero_licenca or "").strip() or None,
        ativo=body.ativo,
        created_by=user.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _arranjo_ser(a, include_docs=True)


@router.put("/arranjos/{arranjo_id}")
async def update_arranjo(
    arranjo_id: int,
    body: ArranjoUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_acervo),
):
    a = db.query(Arranjo).filter(Arranjo.id == arranjo_id).first()
    if not a:
        raise HTTPException(404, "Arranjo não encontrado.")
    data = body.model_dump(exclude_unset=True)
    if "copyright_status" in data and data["copyright_status"]:
        try:
            a.copyright_status = CopyrightStatus(data.pop("copyright_status"))
        except ValueError:
            data.pop("copyright_status", None)
    for k, v in data.items():
        if k in ("titulo_arranjo", "arranjador_nome", "editora", "numero_licenca", "instrumentacao") and isinstance(v, str):
            v = v.strip() or None if k != "instrumentacao" else v.strip()
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return _arranjo_ser(a, include_docs=True)


@router.post("/arranjos/{arranjo_id}/upload", status_code=201)
async def upload_arranjo_documento(
    arranjo_id: int,
    arquivo: UploadFile = File(...),
    tipo: str = Form(...),
    instrumento_nome: Optional[str] = Form(None),
    voz_tipo: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_api_manage_acervo),
):
    a = db.query(Arranjo).filter(Arranjo.id == arranjo_id).first()
    if not a:
        raise HTTPException(404, "Arranjo não encontrado.")
    tipo_norm = (tipo or "").strip().lower()
    if tipo_norm not in {"grade", "instrumento", "coral", "acompanhamento"}:
        raise HTTPException(400, "Tipo inválido. Use: grade, instrumento, coral, acompanhamento.")
    inst = (instrumento_nome or "").strip() or None
    voz = (voz_tipo or "").strip() or None
    caminho, tamanho, _ = salvar_upload(arquivo, a.id, tipo_norm, inst or voz)
    doc = ArranjoDocumento(
        arranjo_id=a.id,
        tipo=tipo_norm,
        instrumento_nome=inst,
        voz_tipo=voz,
        arquivo_caminho=caminho,
        tamanho_bytes=tamanho,
        created_by=user.id,
    )
    db.add(doc)
    db.flush()
    if tipo_norm == "grade":
        a.arquivo_partitura = caminho
    _indexar_documento_best_effort(db, doc, a)
    db.commit()
    db.refresh(doc)
    return _doc_ser(doc)


@router.delete("/arranjos/{arranjo_id}")
async def delete_arranjo(arranjo_id: int, db: Session = Depends(get_db), _: User = Depends(require_api_manage_acervo)):
    a = db.query(Arranjo).filter(Arranjo.id == arranjo_id).first()
    if not a:
        raise HTTPException(404, "Arranjo não encontrado.")
    db.delete(a)
    db.commit()
    return {"ok": True}


# ── Concertos / programação ──────────────────────────────────

@router.get("/concertos")
async def list_concertos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    query = db.query(Concerto)
    total = query.count()
    items = query.order_by(Concerto.data_inicio.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_concerto_ser(c) for c in items]}


@router.post("/concertos", status_code=201)
async def create_concerto(body: ConcertoCreate, db: Session = Depends(get_db), user: User = Depends(require_api_manage_acervo)):
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
    return _concerto_ser(c)


@router.delete("/concertos/{concerto_id}")
async def delete_concerto(concerto_id: int, db: Session = Depends(get_db), _: User = Depends(require_api_manage_acervo)):
    c = db.query(Concerto).filter(Concerto.id == concerto_id).first()
    if not c:
        raise HTTPException(404, "Concerto não encontrado.")
    db.delete(c)
    db.commit()
    return {"ok": True}
