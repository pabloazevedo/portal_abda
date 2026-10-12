"""Dependências da API (/api/v1) — JWT Bearer + checagem de papéis."""
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.mobile_auth import decode_access_token
from app.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)

SYSTEM_ROLES = {
    UserRole.admin.value,
    UserRole.maestro.value,
    UserRole.arquivista.value,
    UserRole.secretaria.value,
}


def _role_value(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def get_current_api_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or (creds.scheme or "").lower() != "bearer" or not creds.credentials:
        raise HTTPException(
            status_code=401,
            detail="Token Bearer ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(creds.credentials)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("typ") != "access":
        raise HTTPException(status_code=401, detail="Tipo de token inválido.")
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuário inativo ou inexistente.")
    request.state.api_user_id = user.id
    return user


def require_musician_user(
    user: User = Depends(get_current_api_user),
) -> User:
    if user.musician_id is None:
        raise HTTPException(
            status_code=403,
            detail="Conta sem vínculo com membro. Solicite ao administrador o vínculo User↔Músico.",
        )
    return user


def require_system_user(user: User = Depends(get_current_api_user)) -> User:
    if _role_value(user) not in SYSTEM_ROLES:
        raise HTTPException(status_code=403, detail="Acesso restrito à equipe operacional.")
    return user


def require_api_admin(user: User = Depends(get_current_api_user)) -> User:
    if _role_value(user) != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
    return user


def require_api_manage_members(user: User = Depends(get_current_api_user)) -> User:
    if _role_value(user) not in {UserRole.admin.value, UserRole.maestro.value, UserRole.secretaria.value}:
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a administradores, maestros e secretaria.",
        )
    return user


def require_api_manage_patrimonio(user: User = Depends(get_current_api_user)) -> User:
    if _role_value(user) not in {UserRole.admin.value, UserRole.arquivista.value}:
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a administradores e arquivistas.",
        )
    return user


def require_api_manage_acervo(user: User = Depends(get_current_api_user)) -> User:
    if _role_value(user) not in {UserRole.admin.value, UserRole.maestro.value, UserRole.arquivista.value}:
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a administradores, maestros e arquivistas.",
        )
    return user


def user_permissions(user: User) -> dict:
    role = _role_value(user)
    return {
        "role": role,
        "is_admin": role == UserRole.admin.value,
        "can_manage_members": role in {UserRole.admin.value, UserRole.maestro.value, UserRole.secretaria.value},
        "can_manage_patrimonio": role in {UserRole.admin.value, UserRole.arquivista.value},
        "can_manage_acervo": role in {UserRole.admin.value, UserRole.maestro.value, UserRole.arquivista.value},
        "is_system_user": role in SYSTEM_ROLES,
    }
