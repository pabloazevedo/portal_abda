"""
Portal — Router de instrumentos.
Fornece o endpoint de busca typeahead para o formulário de membros.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InstrumentoBase

router = APIRouter(prefix="/instrumentos")


@router.get("/search")
async def search_instrumentos(
    q: str = Query("", description="Texto para filtrar instrumentos"),
    limit: int = Query(12, le=50, description="Máximo de resultados"),
    db: Session = Depends(get_db),
):
    """
    Typeahead: retorna instrumentos ativos cujo nome contém *q* (case-insensitive).
    Resultado agrupado por categoria para exibição no dropdown.
    """
    query = db.query(InstrumentoBase).filter(InstrumentoBase.ativo == True)

    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(InstrumentoBase.nome.ilike(term))

    results = (
        query
        .order_by(InstrumentoBase.categoria, InstrumentoBase.nome)
        .limit(limit)
        .all()
    )
    return [
        {"id": r.id, "nome": r.nome, "categoria": r.categoria}
        for r in results
    ]


@router.get("/all")
async def list_all_instrumentos(db: Session = Depends(get_db)):
    """Retorna todos os instrumentos ativos (para pre-load)."""
    results = (
        db.query(InstrumentoBase)
        .filter(InstrumentoBase.ativo == True)
        .order_by(InstrumentoBase.categoria, InstrumentoBase.nome)
        .all()
    )
    return [
        {"id": r.id, "nome": r.nome, "categoria": r.categoria}
        for r in results
    ]
