"""API v1 — autenticação mobile (Android / iOS)."""
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import audit_from_request
from app.database import get_db
from app.limiter import limiter
from app.mobile_auth import (
    create_access_token,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)
from app.api.deps import get_current_api_user, user_permissions
from app.models import User

router = APIRouter(prefix="/auth", tags=["Mobile Auth"])


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=200)
    client: Optional[str] = Field(None, max_length=40, description="android | ios | other")


class RefreshBody(BaseModel):
    refresh_token: str = Field(..., min_length=20)
    client: Optional[str] = Field(None, max_length=40)


class LogoutBody(BaseModel):
    refresh_token: str = Field(..., min_length=20)


def _token_response(user: User, access: str, expires_in: int, refresh: str) -> dict:
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "musician_id": user.musician_id,
            "has_musician_link": bool(user.musician_id),
        },
    }


@router.post("/login", summary="Login do app (Bearer + refresh)")
@limiter.limit("10/minute")
async def api_login(
    request: Request,
    body: Annotated[LoginBody, Body()],
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == body.username.strip()).first()
    if not user or not verify_password(body.password, user.password_hash):
        audit_from_request(
            request,
            action="api.login_failed",
            entity_type="user",
            summary=f"API login falhou: {body.username.strip()}",
        )
        return JSONResponse(status_code=401, content={"detail": "Usuário ou senha inválidos."})
    if not user.is_active:
        return JSONResponse(status_code=401, content={"detail": "Usuário inativo."})

    access, expires_in = create_access_token(user)
    ua = request.headers.get("user-agent")
    refresh = issue_refresh_token(db, user, client=body.client, user_agent=ua)

    # Injeta user na session scope-like para auditoria
    request.session["user"] = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
    }
    audit_from_request(
        request,
        action="api.login",
        entity_type="user",
        entity_id=str(user.id),
        summary=f"API login ({body.client or 'app'}): {user.username}",
        meta={"client": body.client},
    )
    return _token_response(user, access, expires_in, refresh)


@router.post("/refresh", summary="Renovar access token (rotação de refresh)")
@limiter.limit("30/minute")
async def api_refresh(
    request: Request,
    body: Annotated[RefreshBody, Body()],
    db: Session = Depends(get_db),
):
    ua = request.headers.get("user-agent")
    rotated = rotate_refresh_token(db, body.refresh_token, client=body.client, user_agent=ua)
    if not rotated:
        return JSONResponse(status_code=401, content={"detail": "Refresh token inválido ou expirado."})
    user, new_refresh = rotated
    access, expires_in = create_access_token(user)
    return _token_response(user, access, expires_in, new_refresh)


@router.post("/logout", summary="Revogar refresh token")
async def api_logout(
    request: Request,
    body: Annotated[LogoutBody, Body()],
    db: Session = Depends(get_db),
):
    revoke_refresh_token(db, body.refresh_token)
    return {"ok": True}


@router.get("/me", summary="Perfil do usuário autenticado")
async def api_me(user: User = Depends(get_current_api_user)):
    musician = None
    if user.musician:
        m = user.musician
        musician = {
            "id": m.id,
            "full_name": m.full_name,
            "email": m.email,
            "is_active": m.is_active,
        }
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "musician_id": user.musician_id,
        "musician": musician,
        "permissions": user_permissions(user),
    }


# ── Password recovery (SPA) ───────────────────────────────────

class ForgotBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=150)


class ResetBody(BaseModel):
    token: str = Field(..., min_length=10)
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


def _hash_token(raw: str) -> str:
    import hashlib
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/forgot-password", summary="Solicitar redefinição de senha")
@limiter.limit("5/minute")
async def api_forgot_password(
    request: Request,
    body: Annotated[ForgotBody, Body()],
    db: Session = Depends(get_db),
):
    """Sempre retorna ok (anti-enumeração)."""
    import secrets
    from datetime import datetime, timedelta, timezone
    from app.models import PasswordResetToken
    from app.email_utils import send_password_reset

    user = db.query(User).filter(
        User.email == body.email.strip().lower(),
        User.is_active == True,  # noqa: E712
    ).first()
    if user:
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at == None,  # noqa: E711
        ).delete()
        raw = secrets.token_urlsafe(32)
        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(raw),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        ))
        db.commit()
        try:
            smtp_cfg = getattr(request.app.state, "smtp_settings", {})
            send_password_reset(user.email, raw, settings=smtp_cfg)
        except Exception:
            pass
    return {"ok": True, "detail": "Se o e-mail existir, enviaremos instruções."}


@router.post("/reset-password", summary="Redefinir senha com token")
async def api_reset_password(
    body: Annotated[ResetBody, Body()],
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone
    from app.models import PasswordResetToken
    import bcrypt as _bcrypt

    if body.password != body.confirm_password:
        return JSONResponse(status_code=400, content={"detail": "As senhas não coincidem."})
    if len(body.password) < 8:
        return JSONResponse(status_code=400, content={"detail": "Mínimo 8 caracteres."})
    th = _hash_token(body.token)
    record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == th,
        PasswordResetToken.expires_at > datetime.now(timezone.utc),
        PasswordResetToken.used_at == None,  # noqa: E711
    ).first()
    if not record:
        return JSONResponse(status_code=400, content={"detail": "Token inválido ou expirado."})
    record.user.password_hash = _bcrypt.hashpw(
        body.password.encode("utf-8"), _bcrypt.gensalt()
    ).decode("utf-8")
    record.used_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}
