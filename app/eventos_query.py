"""Consulta estática do calendário. Filtros entram só como parâmetros ligados."""
from datetime import datetime, timezone

from sqlalchemy import text

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

EVENTOS_SQL = text("""
    SELECT c.id, c.titulo, c.data_inicio, c.data_fim,
           c.local, c.publico, c.maestro_id,
           m.first_name || ' ' || m.last_name AS maestro_nome,
           COUNT(ca.id) AS num_obras
    FROM concertos c
    LEFT JOIN musicians m ON m.id = c.maestro_id
    LEFT JOIN concerto_arranjos ca ON ca.concerto_id = c.id
    WHERE (CAST(:use_start AS boolean) IS NOT TRUE OR c.data_inicio >= :start)
      AND (CAST(:use_end AS boolean) IS NOT TRUE OR c.data_inicio <= :end)
    GROUP BY c.id, m.first_name, m.last_name
    ORDER BY c.data_inicio
""")


def eventos_params(start: str | None, end: str | None) -> dict:
    params = {
        "use_start": False,
        "use_end": False,
        "start": _EPOCH,
        "end": _EPOCH,
    }
    if start:
        try:
            params["start"] = datetime.fromisoformat(start.replace("Z", "+00:00"))
            params["use_start"] = True
        except ValueError:
            pass
    if end:
        try:
            params["end"] = datetime.fromisoformat(end.replace("Z", "+00:00"))
            params["use_end"] = True
        except ValueError:
            pass
    return params
