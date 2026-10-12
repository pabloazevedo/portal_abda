"""Tickets de curta duração para abrir PDF no mobile sem header Authorization.

Safari/Chrome no smartphone não renderizam bem blob: URLs em iframe.
Com ticket, a página /m/pdf/{ticket} serve o PDF inline (viewer nativo).
"""
from __future__ import annotations

import json
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any

_LOCK = threading.Lock()
_TICKETS: dict[str, "_Ticket"] = {}
DEFAULT_TTL_SECONDS = 10 * 60
REDIS_PREFIX = "pwa:pdf_ticket:"


@dataclass
class _Ticket:
    path: str
    filename: str
    musician_id: int
    expires_at: float


def _purge(now: float | None = None) -> None:
    now = now if now is not None else time.time()
    dead = [k for k, v in _TICKETS.items() if v.expires_at <= now]
    for k in dead:
        _TICKETS.pop(k, None)


def issue_pdf_ticket(
    *,
    path: str,
    filename: str,
    musician_id: int,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    redis_client: Any = None,
) -> tuple[str, int]:
    """Retorna (ticket, expires_in_seconds)."""
    now = time.time()
    ticket = secrets.token_urlsafe(24)
    row = _Ticket(
        path=path,
        filename=filename,
        musician_id=musician_id,
        expires_at=now + ttl_seconds,
    )
    if redis_client is not None:
        try:
            redis_client.setex(
                REDIS_PREFIX + ticket,
                ttl_seconds,
                json.dumps(
                    {
                        "path": row.path,
                        "filename": row.filename,
                        "musician_id": row.musician_id,
                        "expires_at": row.expires_at,
                    }
                ),
            )
            return ticket, ttl_seconds
        except Exception:
            pass
    with _LOCK:
        _purge(now)
        _TICKETS[ticket] = row
    return ticket, ttl_seconds


def consume_pdf_ticket(ticket: str, redis_client: Any = None) -> _Ticket | None:
    """Valida ticket (não remove — permite reload do viewer)."""
    if redis_client is not None:
        try:
            raw = redis_client.get(REDIS_PREFIX + ticket)
            if raw:
                data = json.loads(raw)
                return _Ticket(
                    path=data["path"],
                    filename=data["filename"],
                    musician_id=int(data["musician_id"]),
                    expires_at=float(data["expires_at"]),
                )
            # miss: also try memory (tests / Redis down mid-flight)
        except Exception:
            pass
    now = time.time()
    with _LOCK:
        _purge(now)
        row = _TICKETS.get(ticket)
        if not row or row.expires_at <= now:
            _TICKETS.pop(ticket, None)
            return None
        return row
