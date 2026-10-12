"""Rotas públicas mínimas quando o desktop SPA está ativo (QR / scan)."""
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Patrimonio, PatrimonioEtiqueta

router = APIRouter(tags=["public-spa"])


def _resolve(db: Session, valor: str) -> Patrimonio | None:
    valor = (valor or "").strip()
    if not valor:
        return None
    try:
        uid = UUID(valor)
        item = db.query(Patrimonio).filter(Patrimonio.id == uid).first()
        if item:
            return item
    except (ValueError, TypeError):
        pass
    item = db.query(Patrimonio).filter(Patrimonio.identificador_interno == valor.upper()).first()
    if item:
        return item
    et = (
        db.query(PatrimonioEtiqueta)
        .filter(PatrimonioEtiqueta.valor == valor, PatrimonioEtiqueta.ativo.is_(True))
        .first()
    )
    if et:
        return db.query(Patrimonio).filter(Patrimonio.id == et.patrimonio_id).first()
    return None


@router.get("/patrimonio/scan/{valor}")
async def scan_redirect(valor: str, db: Session = Depends(get_db)):
    item = _resolve(db, valor)
    if not item:
        return RedirectResponse(url="/patrimonio", status_code=302)
    return RedirectResponse(url=f"/patrimonio/{item.id}", status_code=302)


@router.get("/patrimonio/qr/{identificador}")
async def qr_json(identificador: str, db: Session = Depends(get_db)):
    item = (
        db.query(Patrimonio)
        .filter(Patrimonio.identificador_interno == identificador)
        .first()
    )
    if not item:
        return JSONResponse({"detail": "Não encontrado"}, status_code=404)
    return {
        "id": str(item.id),
        "identificador": item.identificador_interno,
        "status": item.status.value if hasattr(item.status, "value") else str(item.status),
        "tipo": item.tipo_label,
    }
