"""API v1 — usuários de sistema."""
from __future__ import annotations

from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_api_admin
from app.app_access import SYSTEM_ROLES
from app.database import get_db
from app.models import User, UserRole

router = APIRouter(prefix="/users", tags=["Users"])


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _serialize(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role.value if hasattr(u.role, "value") else str(u.role),
        "is_active": u.is_active,
        "musician_id": u.musician_id,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _parse_system_role(raw: str) -> UserRole | None:
    try:
        role = UserRole(raw)
    except ValueError:
        return None
    if role not in SYSTEM_ROLES:
        return None
    return role


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=3, max_length=150)
    password: str = Field(..., min_length=6)
    role: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
async def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_api_admin),
):
    users = (
        db.query(User)
        .filter(User.role.in_(list(SYSTEM_ROLES)))
        .order_by(User.username)
        .all()
    )
    return {"items": [_serialize(u) for u in users]}


@router.post("", status_code=201)
async def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_admin),
):
    role = _parse_system_role(body.role)
    if not role:
        raise HTTPException(400, "Papel de sistema inválido.")
    if db.query(User).filter(User.username == body.username.strip()).first():
        raise HTTPException(400, "Username já existe.")
    if db.query(User).filter(User.email == str(body.email).lower()).first():
        raise HTTPException(400, "Email já existe.")
    u = User(
        username=body.username.strip(),
        email=str(body.email).lower(),
        password_hash=_hash(body.password),
        role=role,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return _serialize(u)


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_api_admin),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u or u.role not in SYSTEM_ROLES:
        raise HTTPException(404, "Usuário não encontrado.")
    if body.username is not None:
        u.username = body.username.strip()
    if body.email is not None:
        u.email = str(body.email).lower()
    if body.password:
        u.password_hash = _hash(body.password)
    if body.role is not None:
        role = _parse_system_role(body.role)
        if not role:
            raise HTTPException(400, "Papel de sistema inválido.")
        u.role = role
    if body.is_active is not None:
        if u.id == current.id and body.is_active is False:
            raise HTTPException(400, "Não é possível desativar a si mesmo.")
        u.is_active = body.is_active
    db.commit()
    db.refresh(u)
    return _serialize(u)


@router.post("/{user_id}/toggle-status")
async def toggle_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_api_admin),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u or u.role not in SYSTEM_ROLES:
        raise HTTPException(404, "Usuário não encontrado.")
    if u.id == current.id:
        raise HTTPException(400, "Não é possível desativar a si mesmo.")
    u.is_active = not u.is_active
    db.commit()
    return {"id": u.id, "is_active": u.is_active}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_api_admin),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u or u.role not in SYSTEM_ROLES:
        raise HTTPException(404, "Usuário não encontrado.")
    if u.id == current.id:
        raise HTTPException(400, "Não é possível excluir a si mesmo.")
    db.delete(u)
    db.commit()
    return {"ok": True}
