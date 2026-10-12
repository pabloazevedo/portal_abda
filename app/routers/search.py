"""
Portal — Router de Busca Global.
Retorna músicos, patrimônio e obras que correspondem à query.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Musician, Patrimonio, Obra

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def global_search(q: str = "", db: Session = Depends(get_db)):
    q = q.strip()
    if len(q) < 2:
        return JSONResponse({"musicians": [], "patrimonio": [], "obras": []})

    term = f"%{q}%"

    musicians = (
        db.query(Musician)
        .filter(
            or_(
                Musician.first_name.ilike(term),
                Musician.last_name.ilike(term),
                Musician.email.ilike(term),
                Musician.apelido.ilike(term),
                (Musician.first_name + " " + Musician.last_name).ilike(term),
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

    return JSONResponse({
        "musicians": [
            {
                "id": m.id,
                "name": m.full_name,
                "email": m.email,
                "is_active": m.is_active,
                "url": f"/musicians/{m.id}/edit",
            }
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
            {
                "id": o.id,
                "titulo": o.titulo,
                "compositor": o.compositor_label,
                "url": f"/acervo/obras/{o.id}",
            }
            for o in obras
        ],
    })
