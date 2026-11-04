"""API v1 — patrimônio."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.api.deps import require_api_manage_patrimonio, require_system_user
from app.database import get_db
from app.models import (
    EtiquetaTipo,
    Musician,
    Patrimonio,
    PatrimonioAuditoria,
    PatrimonioEmprestimo,
    PatrimonioEtiqueta,
    StatusPatrimonio,
    TipoItem,
    User,
)
from app.patrimonio_codes import (
    assign_system_codes,
    build_qr_payload,
    render_barcode_png,
    render_qr_png,
)

_TIPO_PREFIX = {
    TipoItem.Instrumento: "INS",
    TipoItem.Movel: "MOV",
    TipoItem.Eletronico: "ELE",
    TipoItem.Partitura: "PAR",
    TipoItem.Decoracao: "DEC",
    TipoItem.Outros: "OUT",
}
_TIPO_SEQ = {
    TipoItem.Instrumento: "seq_patrimonio_ins",
    TipoItem.Movel: "seq_patrimonio_mov",
    TipoItem.Eletronico: "seq_patrimonio_ele",
    TipoItem.Partitura: "seq_patrimonio_par",
    TipoItem.Decoracao: "seq_patrimonio_dec",
    TipoItem.Outros: "seq_patrimonio_out",
}

_SYSTEM_ETIQUETA_TIPOS = {EtiquetaTipo.qr, EtiquetaTipo.barcode_1d}
_NEXTVAL = {
    "seq_patrimonio_ins": text("SELECT nextval('seq_patrimonio_ins')"),
    "seq_patrimonio_mov": text("SELECT nextval('seq_patrimonio_mov')"),
    "seq_patrimonio_ele": text("SELECT nextval('seq_patrimonio_ele')"),
    "seq_patrimonio_par": text("SELECT nextval('seq_patrimonio_par')"),
    "seq_patrimonio_dec": text("SELECT nextval('seq_patrimonio_dec')"),
    "seq_patrimonio_out": text("SELECT nextval('seq_patrimonio_out')"),
}


def _gerar_identificador(db: Session, tipo: TipoItem) -> str:
    prefix = _TIPO_PREFIX.get(tipo, "OUT")
    mes = datetime.now(timezone.utc).strftime("%Y%m")
    seq = _TIPO_SEQ.get(tipo, "seq_patrimonio_out")
    num = db.execute(_NEXTVAL[seq]).scalar()
    return f"{prefix}-{mes}-{num:04d}"


router = APIRouter(prefix="/patrimonio", tags=["Patrimonio"])


def _etiqueta_ser(e: PatrimonioEtiqueta) -> dict:
    tipo = e.tipo.value if hasattr(e.tipo, "value") else str(e.tipo)
    return {
        "id": e.id,
        "tipo": tipo,
        "valor": e.valor,
        "ativo": e.ativo,
        "is_system": e.tipo in _SYSTEM_ETIQUETA_TIPOS,
    }


def _serialize(p: Patrimonio) -> dict:
    emp = p.emprestimo_ativo
    return {
        "id": str(p.id),
        "tipo_item": p.tipo_item.value if hasattr(p.tipo_item, "value") else str(p.tipo_item),
        "tipo_label": p.tipo_label,
        "status": p.status.value if hasattr(p.status, "value") else str(p.status),
        "identificador_interno": p.identificador_interno,
        "qr_payload": p.qr_payload,
        "barcode_value": p.barcode_value,
        "fabricante": p.fabricante,
        "modelo": p.modelo,
        "ano_compra": p.ano_compra,
        "valor_mercado": float(p.valor_mercado) if p.valor_mercado is not None else None,
        "detalhes": p.detalhes or {},
        "observacoes": p.observacoes,
        "etiquetas": [_etiqueta_ser(e) for e in (p.etiquetas or [])],
        "emprestimo_ativo": (
            {
                "id": emp.id,
                "musician_id": emp.musician_id,
                "musician_name": emp.musician.full_name if emp.musician else None,
                "data_emprestimo": emp.data_emprestimo.isoformat() if emp.data_emprestimo else None,
            }
            if emp
            else None
        ),
    }


def _get_item_or_404(db: Session, item_id: UUID) -> Patrimonio:
    item = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    if not item.qr_payload or not item.barcode_value:
        assign_system_codes(db, item)
        db.commit()
        db.refresh(item)
    return item


class PatrimonioCreate(BaseModel):
    tipo_item: str
    status: str = "Disponivel"
    fabricante: Optional[str] = None
    modelo: Optional[str] = None
    ano_compra: Optional[int] = None
    valor_mercado: Optional[float] = None
    observacoes: Optional[str] = None
    detalhes: Optional[dict] = None


class PatrimonioUpdate(BaseModel):
    tipo_item: Optional[str] = None
    status: Optional[str] = None
    fabricante: Optional[str] = None
    modelo: Optional[str] = None
    ano_compra: Optional[int] = None
    valor_mercado: Optional[float] = None
    observacoes: Optional[str] = None
    detalhes: Optional[dict] = None


class LoanBody(BaseModel):
    musician_id: int
    observacoes: Optional[str] = None


class EtiquetaCreate(BaseModel):
    tipo: str
    valor: str


@router.get("")
async def list_patrimonio(
    q: str = "",
    tipo: str = "",
    status: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    query = db.query(Patrimonio)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Patrimonio.identificador_interno.ilike(term),
                Patrimonio.fabricante.ilike(term),
                Patrimonio.modelo.ilike(term),
            )
        )
    if tipo:
        try:
            query = query.filter(Patrimonio.tipo_item == TipoItem(tipo))
        except ValueError:
            pass
    if status:
        try:
            query = query.filter(Patrimonio.status == StatusPatrimonio(status))
        except ValueError:
            pass
    total = query.count()
    items = (
        query.order_by(Patrimonio.identificador_interno)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "page": page, "page_size": page_size, "items": [_serialize(p) for p in items]}


@router.get("/{item_id}")
async def get_patrimonio(
    item_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    p = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not p:
        raise HTTPException(404, "Item não encontrado.")
    return _serialize(p)


@router.post("", status_code=201)
async def create_patrimonio(
    body: PatrimonioCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_patrimonio),
):
    try:
        tipo = TipoItem(body.tipo_item)
        status = StatusPatrimonio(body.status)
    except ValueError as exc:
        raise HTTPException(400, f"Valor inválido: {exc}") from exc
    ident = _gerar_identificador(db, tipo)
    p = Patrimonio(
        tipo_item=tipo,
        status=status,
        identificador_interno=ident,
        fabricante=(body.fabricante or "").strip() or None,
        modelo=(body.modelo or "").strip() or None,
        ano_compra=body.ano_compra,
        valor_mercado=Decimal(str(body.valor_mercado)) if body.valor_mercado is not None else None,
        observacoes=(body.observacoes or "").strip() or None,
        detalhes=body.detalhes or {},
    )
    db.add(p)
    db.flush()
    assign_system_codes(db, p)
    db.commit()
    db.refresh(p)
    return _serialize(p)


@router.put("/{item_id}")
async def update_patrimonio(
    item_id: UUID,
    body: PatrimonioUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_patrimonio),
):
    p = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not p:
        raise HTTPException(404, "Item não encontrado.")
    data = body.model_dump(exclude_unset=True)
    if "tipo_item" in data:
        p.tipo_item = TipoItem(data["tipo_item"])
    if "status" in data:
        p.status = StatusPatrimonio(data["status"])
    for field in ("fabricante", "modelo", "ano_compra", "observacoes", "detalhes"):
        if field in data:
            setattr(p, field, data[field])
    if "valor_mercado" in data:
        p.valor_mercado = Decimal(str(data["valor_mercado"])) if data["valor_mercado"] is not None else None
    db.commit()
    db.refresh(p)
    return _serialize(p)


@router.delete("/{item_id}")
async def delete_patrimonio(
    item_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_patrimonio),
):
    p = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not p:
        raise HTTPException(404, "Item não encontrado.")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/{item_id}/emprestar")
async def emprestar(
    item_id: UUID,
    body: LoanBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_patrimonio),
):
    p = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not p:
        raise HTTPException(404, "Item não encontrado.")
    if p.emprestimo_ativo:
        raise HTTPException(400, "Item já está emprestado.")
    musician = db.query(Musician).filter(Musician.id == body.musician_id).first()
    if not musician:
        raise HTTPException(404, "Membro não encontrado.")
    emp = PatrimonioEmprestimo(
        patrimonio_id=p.id,
        musician_id=musician.id,
        observacoes=body.observacoes,
        data_emprestimo=datetime.now(timezone.utc),
    )
    p.status = StatusPatrimonio.Emprestado
    db.add(emp)
    db.commit()
    db.refresh(p)
    return _serialize(p)


@router.post("/{item_id}/devolver")
async def devolver(
    item_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_patrimonio),
):
    p = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not p:
        raise HTTPException(404, "Item não encontrado.")
    emp = p.emprestimo_ativo
    if not emp:
        raise HTTPException(400, "Item não está emprestado.")
    emp.data_devolucao = datetime.now(timezone.utc)
    p.status = StatusPatrimonio.Disponivel
    db.commit()
    db.refresh(p)
    return _serialize(p)


@router.get("/{item_id}/emprestimos")
async def list_emprestimos(
    item_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    p = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not p:
        raise HTTPException(404, "Item não encontrado.")
    return {
        "items": [
            {
                "id": e.id,
                "musician_id": e.musician_id,
                "musician_name": e.musician.full_name if e.musician else None,
                "data_emprestimo": e.data_emprestimo.isoformat() if e.data_emprestimo else None,
                "data_devolucao": e.data_devolucao.isoformat() if e.data_devolucao else None,
                "observacoes": e.observacoes,
                "ativo": e.data_devolucao is None,
            }
            for e in (p.emprestimos or [])
        ]
    }


@router.get("/{item_id}/etiqueta/qr.png")
async def etiqueta_qr_png(
    item_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    item = _get_item_or_404(db, item_id)
    absolute = str(request.base_url).rstrip("/") + (item.qr_payload or build_qr_payload(item.id))
    png = render_qr_png(absolute)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{item.identificador_interno}-qr.png"'},
    )


@router.get("/{item_id}/etiqueta/barcode.png")
async def etiqueta_barcode_png(
    item_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    item = _get_item_or_404(db, item_id)
    value = item.barcode_value or item.identificador_interno
    png = render_barcode_png(value)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{item.identificador_interno}-barcode.png"'},
    )


@router.get("/{item_id}/etiqueta/print")
async def etiqueta_print(
    item_id: UUID,
    request: Request,
    tipo: str = "ambas",
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    """JSON com URLs absolutas de impressão para a SPA abrir a janela de print."""
    item = _get_item_or_404(db, item_id)
    tipo = (tipo or "ambas").strip().lower()
    if tipo not in {"qr", "barcode", "ambas"}:
        tipo = "ambas"
    base = str(request.base_url).rstrip("/")
    api_base = f"{base}/api/v1/patrimonio/{item.id}"
    return {
        "item": {
            "id": str(item.id),
            "identificador_interno": item.identificador_interno,
            "tipo_label": item.tipo_label,
            "fabricante": item.fabricante,
            "modelo": item.modelo,
            "qr_payload": item.qr_payload,
            "barcode_value": item.barcode_value,
        },
        "print_tipo": tipo,
        "qr_img_url": f"{api_base}/etiqueta/qr.png",
        "barcode_img_url": f"{api_base}/etiqueta/barcode.png",
    }


@router.post("/{item_id}/etiqueta", status_code=201)
async def adicionar_etiqueta(
    item_id: UUID,
    body: EtiquetaCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_api_manage_patrimonio),
):
    item = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not item:
        raise HTTPException(404, "Item não encontrado.")
    try:
        tipo_enum = EtiquetaTipo(body.tipo)
    except ValueError as exc:
        raise HTTPException(400, "Tipo de etiqueta inválido.") from exc
    if tipo_enum in _SYSTEM_ETIQUETA_TIPOS:
        raise HTTPException(400, "QR e código de barras são gerados automaticamente pelo sistema.")
    valor = (body.valor or "").strip()
    if not valor:
        raise HTTPException(400, "Valor da etiqueta não pode ser vazio.")
    conflito = (
        db.query(PatrimonioEtiqueta)
        .filter(
            PatrimonioEtiqueta.tipo == tipo_enum,
            PatrimonioEtiqueta.valor == valor,
            PatrimonioEtiqueta.ativo.is_(True),
        )
        .first()
    )
    if conflito:
        raise HTTPException(400, "Etiqueta já cadastrada neste ou em outro item.")
    etiqueta = PatrimonioEtiqueta(patrimonio_id=item_id, tipo=tipo_enum, valor=valor)
    db.add(etiqueta)
    db.add(
        PatrimonioAuditoria(
            patrimonio_id=item_id,
            acao="etiqueta_adicionada",
            usuario_id=user.id,
            payload={"tipo": body.tipo, "valor": valor},
        )
    )
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/{item_id}/etiqueta/{etiqueta_id}/desativar")
async def desativar_etiqueta(
    item_id: UUID,
    etiqueta_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_api_manage_patrimonio),
):
    etiqueta = (
        db.query(PatrimonioEtiqueta)
        .filter(
            PatrimonioEtiqueta.id == etiqueta_id,
            PatrimonioEtiqueta.patrimonio_id == item_id,
        )
        .first()
    )
    if not etiqueta:
        raise HTTPException(404, "Etiqueta não encontrada.")
    if etiqueta.tipo in _SYSTEM_ETIQUETA_TIPOS:
        raise HTTPException(400, "Não é possível desativar QR/código de barras do sistema.")
    etiqueta.ativo = False
    db.add(
        PatrimonioAuditoria(
            patrimonio_id=item_id,
            acao="etiqueta_desativada",
            usuario_id=user.id,
            payload={"tipo": etiqueta.tipo.value, "valor": etiqueta.valor},
        )
    )
    db.commit()
    item = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    return _serialize(item)
