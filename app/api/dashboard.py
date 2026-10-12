"""API v1 — dashboard / home KPIs."""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.api.deps import require_system_user
from app.database import get_db
from app.models import (
    Concerto,
    Musician,
    Patrimonio,
    StatusPatrimonio,
    TipoItem,
    User,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

_MESES = {
    "pt": ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
           "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
    "es": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
           "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
}


@router.get("")
async def dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_system_user),
    lang: str = "pt",
):
    active_q = db.query(Musician).filter(Musician.is_active == True)  # noqa: E712
    inv_q = db.query(Patrimonio).filter(Patrimonio.status != StatusPatrimonio.Baixa)
    agora = datetime.now(timezone.utc)
    em_7d = agora + timedelta(days=7)
    mes_atual = date.today().month
    mes_nome = _MESES.get(lang, _MESES["pt"])[mes_atual - 1]

    stats = {
        "active": active_q.count(),
        "inv_emprestados": inv_q.filter(Patrimonio.status == StatusPatrimonio.Emprestado).count(),
        "inv_manutencao": inv_q.filter(Patrimonio.status == StatusPatrimonio.Manutencao).count(),
        "eventos_7d": (
            db.query(Concerto)
            .filter(Concerto.data_inicio >= agora, Concerto.data_inicio < em_7d)
            .count()
        ),
        "inv_instrumentos": inv_q.filter(Patrimonio.tipo_item == TipoItem.Instrumento).count(),
        "inv_moveis": inv_q.filter(Patrimonio.tipo_item == TipoItem.Movel).count(),
        "inv_eletronicos": inv_q.filter(Patrimonio.tipo_item == TipoItem.Eletronico).count(),
        "inv_partituras": inv_q.filter(Patrimonio.tipo_item == TipoItem.Partitura).count(),
        "inv_decoracoes": inv_q.filter(Patrimonio.tipo_item == TipoItem.Decoracao).count(),
    }

    proximos_eventos = (
        db.query(Concerto)
        .filter(Concerto.data_inicio >= agora)
        .order_by(Concerto.data_inicio.asc())
        .limit(5)
        .all()
    )
    atencao_itens = (
        inv_q.filter(
            Patrimonio.status.in_([StatusPatrimonio.Emprestado, StatusPatrimonio.Manutencao])
        )
        .order_by(Patrimonio.status.desc())
        .limit(5)
        .all()
    )
    aniversariantes = (
        db.query(Musician)
        .filter(
            Musician.is_active == True,  # noqa: E712
            extract("month", Musician.birth_date) == mes_atual,
        )
        .order_by(extract("day", Musician.birth_date))
        .limit(8)
        .all()
    )

    return {
        "stats": stats,
        "mes_nome": mes_nome,
        "mes_atual": mes_atual,
        "user": {"username": user.username, "role": user.role.value},
        "proximos_eventos": [
            {
                "id": e.id,
                "titulo": e.titulo,
                "data_inicio": e.data_inicio.isoformat() if e.data_inicio else None,
                "local": getattr(e, "local", None) or getattr(e, "local_evento", None),
            }
            for e in proximos_eventos
        ],
        "atencao_itens": [
            {
                "id": str(p.id),
                "identificador": p.identificador_interno,
                "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                "tipo": p.tipo_label,
                "fabricante": p.fabricante or "",
                "modelo": p.modelo or "",
            }
            for p in atencao_itens
        ],
        "aniversariantes": [
            {
                "id": m.id,
                "full_name": m.full_name,
                "birth_date": m.birth_date.isoformat() if m.birth_date else None,
                "photo": m.photo,
            }
            for m in aniversariantes
        ],
    }
