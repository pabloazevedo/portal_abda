"""API v1 — partituras do músico autenticado."""
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import require_musician_user
from app.audit import audit_from_request
from app.database import get_db
from app.models import ArranjoDocumento, ConcertoAcessoPartitura, User
from app.pdf_tickets import issue_pdf_ticket

router = APIRouter(prefix="/me/partituras", tags=["Mobile Partituras"])


def _safe_pdf_filename(title: str) -> str:
    norm = unicodedata.normalize("NFKD", title or "")
    ascii_title = norm.encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^\w\s\-]", "", ascii_title)
    base = re.sub(r"\s+", "_", base.strip())[:80] or "partitura"
    return f"{base}.pdf"


def _aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _window_status(acesso: ConcertoAcessoPartitura, agora: datetime) -> str:
    exp = _aware(acesso.expires_at)
    vf = _aware(acesso.valid_from)
    if exp and agora > exp:
        return "expired"
    if vf and agora < vf:
        return "not_yet_available"
    return "available"


def _doc_title(doc: ArranjoDocumento) -> str:
    """Título amigável (instrumento / tipo), sem hash de arquivo."""
    if doc.instrumento_nome:
        return doc.instrumento_nome
    if doc.stab_tipo:
        return str(doc.stab_tipo).replace("_", " ").title()
    label = doc.tipo_label if hasattr(doc, "tipo_label") else doc.tipo
    return str(label or "Partitura")


def _resolve_available_pdf(db: Session, user: User, acesso_id: int, documento_id: int):
    acesso = (
        db.query(ConcertoAcessoPartitura)
        .filter(
            ConcertoAcessoPartitura.id == acesso_id,
            ConcertoAcessoPartitura.musician_id == user.musician_id,
        )
        .first()
    )
    if not acesso:
        raise HTTPException(status_code=404, detail="Acesso não encontrado.")

    status = _window_status(acesso, datetime.now(timezone.utc))
    if status == "expired":
        raise HTTPException(status_code=403, detail="Acesso expirado.")
    if status == "not_yet_available":
        raise HTTPException(
            status_code=403,
            detail="Partituras disponíveis a partir do dia do evento.",
        )
    if documento_id not in (acesso.documento_ids or []):
        raise HTTPException(status_code=403, detail="Documento não autorizado.")

    doc = db.query(ArranjoDocumento).filter(ArranjoDocumento.id == documento_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    path = Path("uploads") / doc.arquivo_caminho
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return acesso, doc, path


@router.get("", summary="Listar partituras distribuídas ao músico")
@router.get("/", include_in_schema=False)
async def list_my_partituras(
    request: Request,
    user: Annotated[User, Depends(require_musician_user)],
    db: Session = Depends(get_db),
):
    agora = datetime.now(timezone.utc)
    acessos = (
        db.query(ConcertoAcessoPartitura)
        .filter(ConcertoAcessoPartitura.musician_id == user.musician_id)
        .order_by(ConcertoAcessoPartitura.created_at.desc())
        .all()
    )

    items = []
    for acesso in acessos:
        status = _window_status(acesso, agora)
        evento = acesso.concerto
        doc_ids = acesso.documento_ids or []
        docs = []
        if doc_ids:
            rows = db.query(ArranjoDocumento).filter(ArranjoDocumento.id.in_(doc_ids)).all()
            by_id = {d.id: d for d in rows}
            for did in doc_ids:
                d = by_id.get(did)
                if not d:
                    continue
                title = _doc_title(d)
                docs.append({
                    "id": d.id,
                    "tipo": d.tipo,
                    "title": title,
                    "label": title,
                    "instrumento_nome": d.instrumento_nome,
                    "stab_tipo": d.stab_tipo,
                    "download_path": (
                        f"/api/v1/me/partituras/{acesso.id}/documentos/{d.id}/pdf"
                        if status == "available"
                        else None
                    ),
                    "view_ticket_path": (
                        f"/api/v1/me/partituras/{acesso.id}/documentos/{d.id}/view-ticket"
                        if status == "available"
                        else None
                    ),
                })

        items.append({
            "acesso_id": acesso.id,
            "status": status,
            "created_at": _aware(acesso.created_at).isoformat() if acesso.created_at else None,
            "valid_from": _aware(acesso.valid_from).isoformat() if acesso.valid_from else None,
            "expires_at": _aware(acesso.expires_at).isoformat() if acesso.expires_at else None,
            "documento_count": len(docs),
            "evento": {
                "id": evento.id if evento else None,
                "titulo": evento.titulo if evento else None,
                "data_inicio": _aware(evento.data_inicio).isoformat() if evento and evento.data_inicio else None,
                "local": evento.local if evento else None,
            },
            "documentos": docs,
        })

    return {
        "musician_id": user.musician_id,
        "count": len(items),
        "items": items,
        "server_time": agora.isoformat(),
    }


@router.post(
    "/{acesso_id}/documentos/{documento_id}/view-ticket",
    summary="Ticket curto para abrir PDF no viewer mobile",
)
async def create_view_ticket(
    acesso_id: int,
    documento_id: int,
    request: Request,
    user: Annotated[User, Depends(require_musician_user)],
    db: Session = Depends(get_db),
):
    _, doc, path = _resolve_available_pdf(db, user, acesso_id, documento_id)
    title = _doc_title(doc)
    ticket, ttl = issue_pdf_ticket(
        path=str(path),
        filename=_safe_pdf_filename(title),
        musician_id=user.musician_id,
        redis_client=getattr(request.app.state, "redis", None),
    )
    audit_from_request(
        request,
        action="api.partitura_view_ticket",
        entity_type="arranjo_documento",
        entity_id=str(documento_id),
        summary=f"Ticket visualização PDF acesso={acesso_id} doc={documento_id}",
        meta={"acesso_id": acesso_id, "musician_id": user.musician_id},
    )
    return {
        "ticket": ticket,
        "expires_in": ttl,
        "title": title,
        "view_url": f"/m/pdf/{ticket}",
    }


@router.get(
    "/{acesso_id}/documentos/{documento_id}/pdf",
    summary="Abrir PDF da partitura (autenticado)",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_my_pdf(
    acesso_id: int,
    documento_id: int,
    request: Request,
    user: Annotated[User, Depends(require_musician_user)],
    db: Session = Depends(get_db),
):
    _, doc, path = _resolve_available_pdf(db, user, acesso_id, documento_id)
    display_name = _safe_pdf_filename(_doc_title(doc))

    audit_from_request(
        request,
        action="api.partitura_download",
        entity_type="arranjo_documento",
        entity_id=str(documento_id),
        summary=f"Download PDF acesso={acesso_id} doc={documento_id}",
        meta={"acesso_id": acesso_id, "musician_id": user.musician_id},
    )

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=display_name,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{display_name}"',
        },
    )
