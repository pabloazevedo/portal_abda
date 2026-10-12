"""
Portal — Router de Inventário de Patrimônio.
Gerencia ativos, QR Codes e empréstimos para músicos.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.labels import TIPO_LABEL, STATUS_LABEL
from app.models import (
    Patrimonio, PatrimonioEmprestimo, TipoItem, StatusPatrimonio, Musician, InstrumentoBase,
    PatrimonioEtiqueta, PatrimonioAuditoria, EtiquetaTipo,
)
from app.dependencies import make_ctx, get_lang, set_lang_cookie, require_admin, require_manage_patrimonio
from app.patrimonio_codes import (
    assign_system_codes,
    build_qr_payload,
    render_qr_png,
    render_barcode_png,
)
logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/patrimonio")
templates = Jinja2Templates(directory="templates")

# Prefixos por tipo para o identificador_interno
_TIPO_PREFIX = {
    TipoItem.Instrumento: "INS",
    TipoItem.Movel:       "MOV",
    TipoItem.Eletronico:  "ELE",
    TipoItem.Partitura:   "PAR",
    TipoItem.Decoracao:   "DEC",
    TipoItem.Outros:      "OUT",
}

# Sequences PostgreSQL por tipo — eliminam race condition em _gerar_identificador (R-01)
_TIPO_SEQ = {
    TipoItem.Instrumento: "seq_patrimonio_ins",
    TipoItem.Movel:       "seq_patrimonio_mov",
    TipoItem.Eletronico:  "seq_patrimonio_ele",
    TipoItem.Partitura:   "seq_patrimonio_par",
    TipoItem.Decoracao:   "seq_patrimonio_dec",
    TipoItem.Outros:      "seq_patrimonio_out",
}


def _gerar_identificador(db: Session, tipo: TipoItem) -> str:
    """Gera identificador único: PREFIX-YYYYMM-NNNN usando sequence PostgreSQL (R-01)."""
    prefix = _TIPO_PREFIX.get(tipo, "OUT")
    mes = datetime.now(timezone.utc).strftime("%Y%m")
    seq = _TIPO_SEQ.get(tipo, "seq_patrimonio_out")
    num = db.execute(text(f"SELECT nextval('{seq}')")).scalar()
    return f"{prefix}-{mes}-{num:04d}"


def _parse_int(val: str | None) -> Optional[int]:
    if val and str(val).strip().isdigit():
        return int(str(val).strip())
    return None


def _parse_instrumento_base_id(val) -> int:
    """Aceita int, str numérica ou vazio (select oculto em outros tipos)."""
    if val is None or val == "":
        return 0
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return 0


def _parse_float(val: str | None) -> Optional[float]:
    """BUG-01: suporta formato BR com separador de milhar (ex: '1.500,99' → 1500.99)."""
    try:
        if not val or not str(val).strip():
            return None
        cleaned = str(val).strip().replace(".", "").replace(",", ".")
        return float(cleaned)
    except ValueError:
        return None


def _form_error_response(request: Request, db: Session, *, patrimonio, errors: dict, form_data: dict):
    musicians = db.query(Musician).filter(Musician.is_active == True).order_by(
        Musician.first_name, Musician.last_name
    ).all()
    ctx = make_ctx(request, {
        "patrimonio": patrimonio,
        "errors": errors,
        "form_data": form_data,
        "tipos": TipoItem,
        "statuses": StatusPatrimonio,
        "tipo_label": TIPO_LABEL,
        "status_label": STATUS_LABEL,
        "musicians": musicians,
        "inst_por_categoria": _inst_por_categoria(db),
    })
    resp = templates.TemplateResponse("patrimonio/form.html", ctx, status_code=422)
    return set_lang_cookie(resp, get_lang(request))


# ──────────────────────────────────────────────────────────────
# QR Code — endpoint público (sem login) para leitura de QR
# ──────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────
# Scan Universal — resolve qualquer etiqueta (QR, Barcode, RFID)
# GET /patrimonio/scan/{valor}  →  redireciona para /{item_id}
# ──────────────────────────────────────────────────────────────

def _resolve_item_by_scan(db: Session, valor: str) -> Patrimonio | None:
    """Resolve QR/barcode do sistema ou etiquetas ativas."""
    valor = (valor or "").strip()
    if not valor:
        return None

    # UUID direto (payload do QR)
    try:
        uid = UUID(valor)
        item = db.query(Patrimonio).filter(Patrimonio.id == uid).first()
        if item:
            return item
    except (ValueError, TypeError):
        pass

    item = (
        db.query(Patrimonio)
        .filter(
            or_(
                Patrimonio.barcode_value == valor,
                Patrimonio.identificador_interno == valor,
                Patrimonio.qr_payload == valor,
                Patrimonio.qr_payload == f"/patrimonio/scan/{valor}",
            )
        )
        .first()
    )
    if item:
        return item

    etiqueta = (
        db.query(PatrimonioEtiqueta)
        .filter(PatrimonioEtiqueta.valor == valor, PatrimonioEtiqueta.ativo == True)
        .first()
    )
    if etiqueta:
        return db.query(Patrimonio).filter(Patrimonio.id == etiqueta.patrimonio_id).first()
    return None


@router.get("/scan-json/{valor}", response_class=JSONResponse, tags=["scan"])
async def scan_lookup_json(valor: str, db: Session = Depends(get_db)):
    """Lookup de etiqueta retornando JSON — usado pelo widget de teste na área de configurações."""
    item = _resolve_item_by_scan(db, valor)
    if not item:
        return JSONResponse(status_code=404, content={"found": False, "valor": valor})
    return JSONResponse(content={
        "found": True,
        "tipo":                  "sistema",
        "patrimonio_id":         str(item.id),
        "identificador_interno": item.identificador_interno,
        "barcode_value":         item.barcode_value,
        "fabricante":            item.fabricante,
        "modelo":                item.modelo,
        "status":                item.status.value if item.status else None,
        "url":                   f"/patrimonio/{item.id}",
    })


@router.get("/scan/{valor}", response_class=HTMLResponse, tags=["scan"])
async def scan_redirect(valor: str, request: Request, db: Session = Depends(get_db)):
    """Resolve o valor de qualquer etiqueta física para a página do item."""
    item = _resolve_item_by_scan(db, valor)
    if not item:
        raise HTTPException(status_code=404, detail=f"Etiqueta não encontrada: {valor}")
    return RedirectResponse(url=f"/patrimonio/{item.id}", status_code=302)


@router.get("/qr/{identificador}", response_class=JSONResponse, tags=["qr"])
async def qr_detail_json(identificador: str, db: Session = Depends(get_db)):
    """Retorna JSON com dados do item para consumo pelo QR Code."""
    item = db.query(Patrimonio).filter(
        Patrimonio.identificador_interno == identificador
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    emprestimo = item.emprestimo_ativo
    payload = {
        "id":                    str(item.id),
        "identificador_interno": item.identificador_interno,
        "tipo_item":             TIPO_LABEL.get(item.tipo_item, item.tipo_item.value),
        "fabricante":            item.fabricante,
        "modelo":                item.modelo,
        "ano_compra":            item.ano_compra,
        "status":                STATUS_LABEL.get(item.status, item.status.value),
        "detalhes":              item.detalhes or {},
        "observacoes":           item.observacoes,
        "musico_responsavel":    emprestimo.musician.full_name if emprestimo else None,
        "data_emprestimo":       emprestimo.data_emprestimo.isoformat() if emprestimo else None,
    }
    return JSONResponse(content=payload)


# ──────────────────────────────────────────────────────────────
# Listagem
# ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def list_patrimonio(
    request: Request,
    tipo: str = "",
    status: str = "",
    q: str = "",
    page: int = 1,
    db: Session = Depends(get_db),
):
    query = db.query(Patrimonio)

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

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Patrimonio.identificador_interno.ilike(like),
                Patrimonio.fabricante.ilike(like),
                Patrimonio.modelo.ilike(like),
                Patrimonio.observacoes.ilike(like),
            )
        )

    total = query.count()
    per_page = 15
    items = (
        query
        .order_by(Patrimonio.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # Estatísticas rápidas (sempre sobre o total, sem filtros)
    base = db.query(Patrimonio)
    stats = {
        "total":       base.count(),
        "disponivel":  base.filter(Patrimonio.status == StatusPatrimonio.Disponivel).count(),
        "emprestado":  base.filter(Patrimonio.status == StatusPatrimonio.Emprestado).count(),
        "manutencao":  base.filter(Patrimonio.status == StatusPatrimonio.Manutencao).count(),
    }

    ctx = make_ctx(request, {
        "items":      items,
        "total":      total,
        "page":       page,
        "per_page":   per_page,
        "pages":      max(1, (total + per_page - 1) // per_page),
        "q":          q,
        "tipo_filter":   tipo,
        "status_filter": status,
        "tipos":      TipoItem,
        "statuses":   StatusPatrimonio,
        "tipo_label": TIPO_LABEL,
        "status_label": STATUS_LABEL,
        "stats":      stats,
    })
    resp = templates.TemplateResponse("patrimonio/list.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


# ──────────────────────────────────────────────────────────────
# Formulário de criação
# ──────────────────────────────────────────────────────────────

@router.get("/new", response_class=HTMLResponse)
async def new_patrimonio_form(
    request: Request,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_manage_patrimonio),
):
    musicians = db.query(Musician).filter(Musician.is_active == True).order_by(
        Musician.first_name, Musician.last_name
    ).all()
    ctx = make_ctx(request, {
        "patrimonio":  None,
        "errors":      {},
        "form_data":   {},
        "tipos":       TipoItem,
        "statuses":    StatusPatrimonio,
        "tipo_label":  TIPO_LABEL,
        "status_label": STATUS_LABEL,
        "musicians":   musicians,
        "inst_por_categoria": _inst_por_categoria(db),
    })
    resp = templates.TemplateResponse("patrimonio/form.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


# ──────────────────────────────────────────────────────────────
# Criar item
# ──────────────────────────────────────────────────────────────

@router.post("/new", response_class=HTMLResponse)
async def create_patrimonio(
    request: Request,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_manage_patrimonio),
    tipo_item: str        = Form(...),
    fabricante: str       = Form(""),
    modelo: str           = Form(""),
    ano_compra: str       = Form(""),
    valor_mercado: str    = Form(""),
    observacoes: str      = Form(""),
    # Instrumento (str: select oculto envia "" em outros tipos)
    instrumento_base_id: str  = Form(""),
    ano_fabricacao: str       = Form(""),
    avaliacao_condicao: str   = Form(""),
    # Partitura
    compositor: str    = Form(""),
    arranjador: str    = Form(""),
    nome_obra: str     = Form(""),
    # Decoração / Outros
    descricao_livre: str       = Form(""),
    local_armazenamento: str   = Form(""),
):
    inst_id = _parse_instrumento_base_id(instrumento_base_id)

    # Resolve nome/categoria do instrumento base
    instrumento_nome = ""
    instrumento_categoria = ""
    if inst_id:
        inst_obj = db.query(InstrumentoBase).filter(InstrumentoBase.id == inst_id).first()
        if inst_obj:
            instrumento_nome = inst_obj.nome
            instrumento_categoria = inst_obj.categoria

    errors: dict = {}
    form_data = {
        "tipo_item": tipo_item, "fabricante": fabricante, "modelo": modelo,
        "ano_compra": ano_compra, "valor_mercado": valor_mercado,
        "observacoes": observacoes, "instrumento_base_id": inst_id,
        "instrumento_nome": instrumento_nome, "instrumento_categoria": instrumento_categoria,
        "ano_fabricacao": ano_fabricacao, "avaliacao_condicao": avaliacao_condicao,
        "compositor": compositor, "arranjador": arranjador, "nome_obra": nome_obra,
        "descricao_livre": descricao_livre, "local_armazenamento": local_armazenamento,
    }

    # Validação do tipo
    try:
        tipo_enum = TipoItem(tipo_item)
    except ValueError:
        errors["tipo_item"] = "Selecione um tipo válido"
        tipo_enum = None

    # Validações específicas por tipo
    if tipo_enum == TipoItem.Partitura and not nome_obra.strip():
        errors["nome_obra"] = "Nome da obra é obrigatório para Partitura"

    if tipo_enum == TipoItem.Instrumento and not inst_id:
        errors["instrumento_base_id"] = "Selecione o instrumento"

    if errors:
        return _form_error_response(
            request, db, patrimonio=None, errors=errors, form_data=form_data
        )

    # Monta JSONB de detalhes conforme tipo
    detalhes = _build_detalhes(tipo_enum, form_data)

    id_interno = _gerar_identificador(db, tipo_enum)

    item = Patrimonio(
        tipo_item             = tipo_enum,
        status                = StatusPatrimonio.Disponivel,
        identificador_interno = id_interno,
        fabricante            = fabricante.strip() or None,
        modelo                = modelo.strip() or None,
        ano_compra            = _parse_int(ano_compra),
        valor_mercado         = _parse_float(valor_mercado),
        detalhes              = detalhes or None,
        observacoes           = observacoes.strip() or None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    assign_system_codes(db, item)
    logger.info(
        f"[PATRIMÔNIO] Novo item criado: {item.identificador_interno} "
        f"qr={item.qr_payload} barcode={item.barcode_value}"
    )
    db.add(PatrimonioAuditoria(
        patrimonio_id=item.id,
        acao="criado",
        usuario_id=_user["id"],
        payload={
            "identificador_interno": item.identificador_interno,
            "tipo": item.tipo_item.value,
            "qr_payload": item.qr_payload,
            "barcode_value": item.barcode_value,
        },
    ))
    db.commit()
    return RedirectResponse(url=f"/patrimonio/{item.id}", status_code=303)


# ──────────────────────────────────────────────────────────────
# Detalhe do item (+ QR code visual)
# ──────────────────────────────────────────────────────────────

@router.get("/{item_id}", response_class=HTMLResponse)
async def detail_patrimonio(
    item_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    item = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    # Garante códigos do sistema (itens legados)
    if not item.qr_payload or not item.barcode_value:
        assign_system_codes(db, item)
        db.commit()
        db.refresh(item)

    musicians = db.query(Musician).filter(Musician.is_active == True).order_by(
        Musician.first_name, Musician.last_name
    ).all()

    etiquetas_extras = [
        e for e in (item.etiquetas or [])
        if e.ativo and e.tipo not in (EtiquetaTipo.qr, EtiquetaTipo.barcode_1d)
    ]

    ctx = make_ctx(request, {
        "item":         item,
        "tipo_label":   TIPO_LABEL,
        "status_label": STATUS_LABEL,
        "musicians":    musicians,
        "etiquetas_extras": etiquetas_extras,
    })
    resp = templates.TemplateResponse("patrimonio/detail.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


# ──────────────────────────────────────────────────────────────
# Editar item
# ──────────────────────────────────────────────────────────────

@router.get("/{item_id}/edit", response_class=HTMLResponse)
async def edit_patrimonio_form(
    item_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_manage_patrimonio),
):
    item = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    musicians = db.query(Musician).filter(Musician.is_active == True).order_by(
        Musician.first_name, Musician.last_name
    ).all()

    det = item.detalhes or {}
    form_data = {
        "tipo_item":           item.tipo_item.value,
        "fabricante":          item.fabricante or "",
        "modelo":              item.modelo or "",
        "ano_compra":          str(item.ano_compra) if item.ano_compra else "",
        "valor_mercado":       str(item.valor_mercado) if item.valor_mercado else "",
        "observacoes":         item.observacoes or "",
        "instrumento_base_id":   det.get("instrumento_base_id", ""),
        "instrumento_nome":      det.get("instrumento_nome", ""),
        "instrumento_categoria": det.get("instrumento_categoria", ""),
        "ano_fabricacao":        str(det.get("ano_fabricacao", "")),
        "avaliacao_condicao":    det.get("avaliacao_condicao", ""),
        "compositor":          det.get("compositor", ""),
        "arranjador":          det.get("arranjador", ""),
        "nome_obra":           det.get("nome_obra", ""),
        "descricao_livre":     det.get("descricao_livre", ""),
        "local_armazenamento": det.get("local_armazenamento", ""),
    }

    ctx = make_ctx(request, {
        "patrimonio":  item,
        "errors":      {},
        "form_data":   form_data,
        "tipos":       TipoItem,
        "statuses":    StatusPatrimonio,
        "tipo_label":  TIPO_LABEL,
        "status_label": STATUS_LABEL,
        "musicians":   musicians,
        "inst_por_categoria": _inst_por_categoria(db),
    })
    resp = templates.TemplateResponse("patrimonio/form.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/{item_id}/edit", response_class=HTMLResponse)
async def update_patrimonio(
    item_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_manage_patrimonio),
    tipo_item: str        = Form(...),
    status: str           = Form(...),
    fabricante: str       = Form(""),
    modelo: str           = Form(""),
    ano_compra: str       = Form(""),
    valor_mercado: str    = Form(""),
    observacoes: str      = Form(""),
    instrumento_base_id: str  = Form(""),
    ano_fabricacao: str       = Form(""),
    avaliacao_condicao: str   = Form(""),
    compositor: str    = Form(""),
    arranjador: str    = Form(""),
    nome_obra: str     = Form(""),
    descricao_livre: str       = Form(""),
    local_armazenamento: str   = Form(""),
):
    item = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    inst_id = _parse_instrumento_base_id(instrumento_base_id)

    # Resolve nome/categoria do instrumento base
    instrumento_nome = ""
    instrumento_categoria = ""
    if inst_id:
        inst_obj = db.query(InstrumentoBase).filter(InstrumentoBase.id == inst_id).first()
        if inst_obj:
            instrumento_nome = inst_obj.nome
            instrumento_categoria = inst_obj.categoria

    errors: dict = {}
    form_data = {
        "tipo_item": tipo_item, "status": status, "fabricante": fabricante,
        "modelo": modelo, "ano_compra": ano_compra, "valor_mercado": valor_mercado,
        "observacoes": observacoes, "instrumento_base_id": inst_id,
        "instrumento_nome": instrumento_nome, "instrumento_categoria": instrumento_categoria,
        "ano_fabricacao": ano_fabricacao, "avaliacao_condicao": avaliacao_condicao,
        "compositor": compositor, "arranjador": arranjador, "nome_obra": nome_obra,
        "descricao_livre": descricao_livre, "local_armazenamento": local_armazenamento,
    }

    try:
        tipo_enum = TipoItem(tipo_item)
    except ValueError:
        errors["tipo_item"] = "Tipo inválido"
        tipo_enum = item.tipo_item

    try:
        status_enum = StatusPatrimonio(status)
    except ValueError:
        errors["status"] = "Status inválido"
        status_enum = item.status

    if tipo_enum == TipoItem.Partitura and not nome_obra.strip():
        errors["nome_obra"] = "Nome da obra é obrigatório para Partitura"

    if tipo_enum == TipoItem.Instrumento and not inst_id:
        errors["instrumento_base_id"] = "Selecione o instrumento"

    if errors:
        return _form_error_response(
            request, db, patrimonio=item, errors=errors, form_data=form_data
        )

    detalhes = _build_detalhes(tipo_enum, form_data)

    # Se mudar status manualmente para Disponivel mas há empréstimo ativo → erro
    if status_enum == StatusPatrimonio.Disponivel and item.emprestimo_ativo:
        errors["status"] = "Item possui empréstimo ativo. Devolva-o antes de marcar como Disponível."
        return _form_error_response(
            request, db, patrimonio=item, errors=errors, form_data=form_data
        )

    item.tipo_item     = tipo_enum
    item.status        = status_enum
    item.fabricante    = fabricante.strip() or None
    item.modelo        = modelo.strip() or None
    item.ano_compra    = _parse_int(ano_compra)
    item.valor_mercado = _parse_float(valor_mercado)
    item.detalhes      = detalhes or None
    item.observacoes   = observacoes.strip() or None
    # I-03: updated_at é gerenciado pelo onupdate do ORM — não atribuir manualmente

    db.commit()
    return RedirectResponse(url=f"/patrimonio/{item.id}", status_code=303)


# ──────────────────────────────────────────────────────────────
# Excluir item
# ──────────────────────────────────────────────────────────────

@router.post("/{item_id}/delete")
async def delete_patrimonio(
    item_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    item = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    if item.emprestimo_ativo:
        return RedirectResponse(
            url=f"/patrimonio/{item_id}?erro=Item+com+empréstimo+ativo+não+pode+ser+excluído",
            status_code=303,
        )

    db.delete(item)
    db.commit()
    return RedirectResponse(url="/patrimonio/", status_code=303)


# ──────────────────────────────────────────────────────────────
# Vincular item a músico (empréstimo)
# ──────────────────────────────────────────────────────────────

@router.post("/{item_id}/vincular")
async def vincular_patrimonio(
    item_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_manage_patrimonio),
    musician_id: int  = Form(...),
    observacoes: str  = Form(""),
):
    item = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    if item.status == StatusPatrimonio.Emprestado:
        return RedirectResponse(
            url=f"/patrimonio/{item_id}?erro=Item+já+está+emprestado",
            status_code=303,
        )

    if item.status == StatusPatrimonio.Baixa:
        return RedirectResponse(
            url=f"/patrimonio/{item_id}?erro=Item+com+status+Baixa+não+pode+ser+emprestado",
            status_code=303,
        )

    musician = db.query(Musician).filter(Musician.id == musician_id).first()
    if not musician:
        raise HTTPException(status_code=404, detail="Músico não encontrado")

    emprestimo = PatrimonioEmprestimo(
        patrimonio_id   = item.id,
        musician_id     = musician_id,
        observacoes     = observacoes.strip() or None,
    )
    db.add(emprestimo)
    item.status = StatusPatrimonio.Emprestado
    # I-03: updated_at gerenciado pelo ORM
    db.commit()
    logger.info(f"[PATRIMÔNIO] {item.identificador_interno} vinculado ao músico {musician.full_name}")
    db.add(PatrimonioAuditoria(
        patrimonio_id=item_id,
        acao="emprestado",
        usuario_id=_user["id"],
        payload={"musician_id": musician_id, "musician_nome": musician.full_name},
    ))
    db.commit()
    return RedirectResponse(url=f"/patrimonio/{item_id}", status_code=303)


# ──────────────────────────────────────────────────────────────
# Desvincular (devolver)
# ──────────────────────────────────────────────────────────────

@router.post("/{item_id}/desvincular/{emprestimo_id}")
async def desvincular_patrimonio(
    item_id: UUID,
    emprestimo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_manage_patrimonio),
):
    emprestimo = db.query(PatrimonioEmprestimo).filter(
        PatrimonioEmprestimo.id == emprestimo_id,
        PatrimonioEmprestimo.patrimonio_id == item_id,
        PatrimonioEmprestimo.data_devolucao == None,
    ).first()

    if not emprestimo:
        raise HTTPException(status_code=404, detail="Empréstimo ativo não encontrado")

    emprestimo.data_devolucao = datetime.now(timezone.utc)
    emprestimo.patrimonio.status = StatusPatrimonio.Disponivel
    # I-03: updated_at gerenciado pelo ORM
    db.commit()
    db.add(PatrimonioAuditoria(
        patrimonio_id=item_id,
        acao="devolvido",
        usuario_id=_user["id"],
        payload={"emprestimo_id": emprestimo_id},
    ))
    db.commit()
    return RedirectResponse(url=f"/patrimonio/{item_id}", status_code=303)


# ──────────────────────────────────────────────────────────────
# Etiquetas — QR/barcode do sistema + impressão + RFID opcional
# ──────────────────────────────────────────────────────────────

_ETIQUETA_LABEL = {
    EtiquetaTipo.qr:          "QR Code",
    EtiquetaTipo.barcode_1d:  "Barcode 1D",
    EtiquetaTipo.data_matrix: "Data Matrix",
    EtiquetaTipo.rfid_hf:     "RFID HF",
    EtiquetaTipo.rfid_uhf:    "RFID UHF",
}

_SYSTEM_ETIQUETA_TIPOS = {EtiquetaTipo.qr, EtiquetaTipo.barcode_1d}


def _get_item_or_404(db: Session, item_id: UUID) -> Patrimonio:
    item = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    if not item.qr_payload or not item.barcode_value:
        assign_system_codes(db, item)
        db.commit()
        db.refresh(item)
    return item


@router.get("/{item_id}/etiqueta/qr.png")
async def etiqueta_qr_png(
    item_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    """PNG do QR Code gerado pelo sistema (para tela e impressoras)."""
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
):
    """PNG Code128 do código de barras gerado pelo sistema."""
    item = _get_item_or_404(db, item_id)
    value = item.barcode_value or item.identificador_interno
    png = render_barcode_png(value)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{item.identificador_interno}-barcode.png"'},
    )


@router.get("/{item_id}/etiqueta/imprimir", response_class=HTMLResponse)
async def etiqueta_imprimir(
    item_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    tipo: str = "ambas",
):
    """Página de impressão formatada para impressoras de etiquetas."""
    item = _get_item_or_404(db, item_id)
    tipo = (tipo or "ambas").strip().lower()
    if tipo not in {"qr", "barcode", "ambas"}:
        tipo = "ambas"
    ctx = make_ctx(request, {
        "item": item,
        "print_tipo": tipo,
        "qr_img_url": f"/patrimonio/{item.id}/etiqueta/qr.png",
        "barcode_img_url": f"/patrimonio/{item.id}/etiqueta/barcode.png",
    })
    return templates.TemplateResponse("patrimonio/etiqueta_print.html", ctx)


@router.post("/{item_id}/etiqueta", response_class=HTMLResponse)
async def adicionar_etiqueta(
    item_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_manage_patrimonio),
    tipo: str  = Form(...),
    valor: str = Form(...),
):
    item = db.query(Patrimonio).filter(Patrimonio.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    try:
        tipo_enum = EtiquetaTipo(tipo)
    except ValueError:
        return RedirectResponse(
            url=f"/patrimonio/{item_id}?erro=Tipo+de+etiqueta+inválido",
            status_code=303,
        )

    if tipo_enum in _SYSTEM_ETIQUETA_TIPOS:
        return RedirectResponse(
            url=f"/patrimonio/{item_id}?erro=QR+e+código+de+barras+são+gerados+automaticamente+pelo+sistema",
            status_code=303,
        )

    valor = valor.strip()
    if not valor:
        return RedirectResponse(
            url=f"/patrimonio/{item_id}?erro=Valor+da+etiqueta+não+pode+ser+vazio",
            status_code=303,
        )

    conflito = db.query(PatrimonioEtiqueta).filter(
        PatrimonioEtiqueta.tipo == tipo_enum,
        PatrimonioEtiqueta.valor == valor,
        PatrimonioEtiqueta.ativo == True,
    ).first()
    if conflito:
        return RedirectResponse(
            url=f"/patrimonio/{item_id}?erro=Etiqueta+já+cadastrada+neste+ou+em+outro+item",
            status_code=303,
        )

    db.add(PatrimonioEtiqueta(patrimonio_id=item_id, tipo=tipo_enum, valor=valor))
    db.add(PatrimonioAuditoria(
        patrimonio_id=item_id,
        acao="etiqueta_adicionada",
        usuario_id=_user["id"],
        payload={"tipo": tipo, "valor": valor},
    ))
    db.commit()
    logger.info(f"[PATRIMÔNIO] Etiqueta {tipo}/{valor} adicionada ao item {item.identificador_interno}")
    return RedirectResponse(url=f"/patrimonio/{item_id}", status_code=303)


@router.post("/{item_id}/etiqueta/{etiqueta_id}/desativar")
async def desativar_etiqueta(
    item_id: UUID,
    etiqueta_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_manage_patrimonio),
):
    etiqueta = db.query(PatrimonioEtiqueta).filter(
        PatrimonioEtiqueta.id == etiqueta_id,
        PatrimonioEtiqueta.patrimonio_id == item_id,
    ).first()
    if not etiqueta:
        raise HTTPException(status_code=404, detail="Etiqueta não encontrada")

    if etiqueta.tipo in _SYSTEM_ETIQUETA_TIPOS:
        return RedirectResponse(
            url=f"/patrimonio/{item_id}?erro=Não+é+possível+desativar+QR/código+de+barras+do+sistema",
            status_code=303,
        )

    etiqueta.ativo = False
    db.add(PatrimonioAuditoria(
        patrimonio_id=item_id,
        acao="etiqueta_desativada",
        usuario_id=_user["id"],
        payload={"tipo": etiqueta.tipo.value, "valor": etiqueta.valor},
    ))
    db.commit()
    logger.info(f"[PATRIMÔNIO] Etiqueta {etiqueta.tipo.value}/{etiqueta.valor} desativada")
    return RedirectResponse(url=f"/patrimonio/{item_id}", status_code=303)


# ──────────────────────────────────────────────────────────────
# Helper: monta JSONB de detalhes por tipo
# ──────────────────────────────────────────────────────────────

def _inst_por_categoria(db: Session) -> dict:
    """Retorna instrumentos ativos agrupados por categoria, preservando ordem."""
    insts = (
        db.query(InstrumentoBase)
        .filter(InstrumentoBase.ativo == True)
        .order_by(InstrumentoBase.categoria, InstrumentoBase.nome)
        .all()
    )
    result: dict = {}
    for inst in insts:
        result.setdefault(inst.categoria, []).append(inst)
    return result


def _build_detalhes(tipo: TipoItem, form: dict) -> dict:
    if tipo == TipoItem.Instrumento:
        return {k: v for k, v in {
            "instrumento_base_id":   _parse_int(str(form.get("instrumento_base_id", ""))),
            "instrumento_nome":      form.get("instrumento_nome", "").strip() or None,
            "instrumento_categoria": form.get("instrumento_categoria", "").strip() or None,
            "ano_fabricacao":        _parse_int(form.get("ano_fabricacao")),
            "avaliacao_condicao":    form.get("avaliacao_condicao", "").strip() or None,
        }.items() if v is not None}

    if tipo == TipoItem.Partitura:
        return {k: v for k, v in {
            "nome_obra":  form.get("nome_obra", "").strip() or None,
            "compositor": form.get("compositor", "").strip() or None,
            "arranjador": form.get("arranjador", "").strip() or None,
        }.items() if v is not None}

    if tipo == TipoItem.Decoracao or tipo == TipoItem.Outros:
        return {k: v for k, v in {
            "descricao_livre":     form.get("descricao_livre", "").strip() or None,
            "local_armazenamento": form.get("local_armazenamento", "").strip() or None,
        }.items() if v is not None}

    return {}
