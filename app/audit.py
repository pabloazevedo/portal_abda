"""
Auditoria de ações do sistema (quem fez o quê).
Gravação best-effort em sessão própria — não quebra a request se falhar.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AuditLog, Configuracao

logger = logging.getLogger("uvicorn.error")

AUDIT_RETENTION_MIN = 7
AUDIT_RETENTION_MAX = 90  # 3 meses
AUDIT_RETENTION_DEFAULT = 90

SKIP_AUDIT_PREFIXES = (
    "/static",
    "/uploads",
    "/favicon",
    "/healthz",
    "/readyz",
    "/settings/health",
    "/instrumentos",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
)
SKIP_AUDIT_EXACT = {
    "/search",
    "/musicians/organogram/data",
    "/login",
    "/logout",
    "/settings/auditoria/retencao",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
}


def clamp_retention_days(days: int | None) -> int:
    try:
        n = int(days) if days is not None else AUDIT_RETENTION_DEFAULT
    except (TypeError, ValueError):
        n = AUDIT_RETENTION_DEFAULT
    return max(AUDIT_RETENTION_MIN, min(AUDIT_RETENTION_MAX, n))


def get_retention_days(db: Session | None = None) -> int:
    own = False
    if db is None:
        db = SessionLocal()
        own = True
    try:
        cfg = db.query(Configuracao).filter(Configuracao.id == 1).first()
        if cfg is None:
            return AUDIT_RETENTION_DEFAULT
        return clamp_retention_days(getattr(cfg, "audit_retention_days", None))
    except Exception:
        logger.exception("[Portal] Falha ao ler retenção de auditoria")
        return AUDIT_RETENTION_DEFAULT
    finally:
        if own:
            db.close()


def write_audit(
    *,
    actor_user_id: int | None,
    actor_username: str | None,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    summary: str = "",
    ip: str | None = None,
    request_id: str | None = None,
    meta: dict | None = None,
) -> None:
    """Persiste um evento de auditoria. Nunca propaga exceção ao caller."""
    try:
        db = SessionLocal()
        try:
            row = AuditLog(
                actor_user_id=actor_user_id,
                actor_username=(actor_username or "")[:100] or None,
                action=(action or "unknown")[:80],
                entity_type=(entity_type or "")[:80] or None,
                entity_id=(entity_id or "")[:80] or None,
                summary=(summary or "")[:500] or None,
                ip=(ip or "")[:64] or None,
                request_id=(request_id or "")[:64] or None,
                meta_json=json.dumps(meta, ensure_ascii=False) if meta else None,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("[Portal] Falha ao gravar auditoria action=%s", action)


def audit_from_request(
    request,
    *,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    summary: str = "",
    meta: dict | None = None,
) -> None:
    user = (getattr(request, "session", None) or {}).get("user") or {}
    ip = None
    try:
        ip = request.client.host if request.client else None
    except Exception:
        pass
    rid = getattr(getattr(request, "state", None), "request_id", None)
    write_audit(
        actor_user_id=user.get("id"),
        actor_username=user.get("username"),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else "",
        summary=summary,
        ip=ip,
        request_id=rid,
        meta=meta,
    )


def should_auto_audit(method: str, path: str) -> bool:
    if method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    if path in SKIP_AUDIT_EXACT:
        return False
    if any(path.startswith(p) for p in SKIP_AUDIT_PREFIXES):
        return False
    # Evita ruido de health JSON e probes
    if path.endswith("/health") or path in {"/healthz", "/readyz"}:
        return False
    return True


def summarize_http(method: str, path: str, status: int) -> tuple[str, str, str, str]:
    """Retorna action, entity_type, entity_id, summary."""
    parts = [p for p in path.strip("/").split("/") if p]
    entity_type = parts[0] if parts else "app"
    entity_id = ""
    for p in reversed(parts):
        if p.isdigit() or (len(p) == 36 and p.count("-") == 4):
            entity_id = p
            break
    action = f"{method.lower()}.{entity_type}"
    summary = f"{method} {path} → {status}"
    return action, entity_type, entity_id, summary


def purge_expired_logs(retention_days: int | None = None) -> int:
    """Apaga logs fora da janela. Retorna quantidade removida."""
    days = clamp_retention_days(retention_days if retention_days is not None else get_retention_days())
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        q = db.query(AuditLog).filter(AuditLog.created_at < cutoff)
        count = q.count()
        if count:
            q.delete(synchronize_session=False)
            db.commit()
            # Registra o próprio purge (fica dentro da janela)
            write_audit(
                actor_user_id=None,
                actor_username="system",
                action="audit.purge",
                entity_type="audit_log",
                summary=f"Expurgo automático: {count} registro(s) anteriores a {days} dia(s).",
                meta={"deleted": count, "retention_days": days, "cutoff": cutoff.isoformat()},
            )
        return count
    except Exception:
        logger.exception("[Portal] Falha no expurgo de auditoria")
        db.rollback()
        return 0
    finally:
        db.close()
