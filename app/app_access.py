"""
Acesso ao App / PWA para membros (músicos e coralistas).

Usuários de sistema (admin, maestro, arquivista, secretaria) vivem em /users.
Contas de app são User(role=user) vinculadas a musicians.musician_id.
"""

from __future__ import annotations

import re
import secrets
import string

import bcrypt
from sqlalchemy.orm import Session

from app.mobile_auth import revoke_all_user_tokens
from app.models import Musician, User, UserRole

SYSTEM_ROLES = {UserRole.admin, UserRole.maestro, UserRole.arquivista, UserRole.secretaria}


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def get_app_user(db: Session, musician_id: int) -> User | None:
    return (
        db.query(User)
        .filter(User.musician_id == musician_id)
        .first()
    )


def has_app_access(db: Session, musician_id: int) -> bool:
    user = get_app_user(db, musician_id)
    return bool(user and user.is_active)


def _username_from_email(email: str, musician_id: int) -> str:
    local = (email or "").split("@")[0].strip().lower()
    local = re.sub(r"[^a-z0-9._-]", "", local)[:40]
    if not local:
        local = f"membro{musician_id}"
    return local


def _unique_username(db: Session, base: str, exclude_user_id: int | None = None) -> str:
    candidate = base[:50]
    n = 0
    while True:
        q = db.query(User).filter(User.username == candidate)
        if exclude_user_id is not None:
            q = q.filter(User.id != exclude_user_id)
        if not q.first():
            return candidate
        n += 1
        suffix = f"_{n}"
        candidate = f"{base[:50 - len(suffix)]}{suffix}"


def generate_temp_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def grant_app_access(
    db: Session,
    musician: Musician,
    password: str,
) -> User:
    """Cria ou reativa conta de app (role=user) vinculada ao membro."""
    existing = get_app_user(db, musician.id)
    email = musician.email.strip().lower()

    if existing:
        existing.email = email
        existing.password_hash = _hash(password)
        existing.is_active = True
        existing.role = UserRole.user
        existing.musician_id = musician.id
        db.flush()
        return existing

    # E-mail já usado por usuário de sistema → não sobrescrever
    by_email = db.query(User).filter(User.email == email).first()
    if by_email:
        if by_email.role in SYSTEM_ROLES:
            raise ValueError(
                "Este e-mail já pertence a um usuário de sistema. "
                "Use outro e-mail no membro ou vincule o acesso pelo admin."
            )
        # Conta app órfã / sem vínculo: reaproveita
        by_email.musician_id = musician.id
        by_email.password_hash = _hash(password)
        by_email.is_active = True
        by_email.role = UserRole.user
        db.flush()
        return by_email

    username = _unique_username(db, _username_from_email(email, musician.id))
    user = User(
        username=username,
        email=email,
        password_hash=_hash(password),
        role=UserRole.user,
        is_active=True,
        musician_id=musician.id,
    )
    db.add(user)
    db.flush()
    return user


def revoke_app_access(db: Session, musician_id: int) -> bool:
    """Remove acesso ao app: desativa conta app e desvincula. Retorna True se havia acesso."""
    user = get_app_user(db, musician_id)
    if user is None:
        return False

    revoke_all_user_tokens(db, user.id)

    if user.role == UserRole.user:
        # Conta exclusiva do app — desativa e desvincula (mantém histórico no /users filtrado)
        user.musician_id = None
        user.is_active = False
    else:
        # Usuário de sistema que estava vinculado — só desvincula o app
        user.musician_id = None

    db.flush()
    return True


def set_app_password(db: Session, musician_id: int, password: str) -> bool:
    user = get_app_user(db, musician_id)
    if user is None or not user.is_active:
        return False
    user.password_hash = _hash(password)
    db.flush()
    return True
