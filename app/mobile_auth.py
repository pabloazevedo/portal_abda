"""
Autenticação JWT + refresh tokens para apps Android/iOS.
Boas práticas: access curto, refresh rotativo, HTTPS, Bearer.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.models import ApiRefreshToken, User

logger = logging.getLogger("uvicorn.error")

# Access token curto (Google/Apple: preferir sessões curtas + refresh)
ACCESS_TOKEN_MINUTES = int(os.getenv("API_ACCESS_TOKEN_MINUTES", "30"))
REFRESH_TOKEN_DAYS = int(os.getenv("API_REFRESH_TOKEN_DAYS", "30"))
JWT_ALG = "HS256"
JWT_ISSUER = os.getenv("API_JWT_ISSUER", "orchestra-portal")
JWT_AUDIENCE = os.getenv("API_JWT_AUDIENCE", "orchestra-mobile")


def _jwt_secret() -> str:
    sk = os.getenv("SECRET_KEY") or "change-me-in-production-use-32-random-chars"
    return f"{sk}:mobile-api-v1"


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user: User) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    payload = {
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": str(user.id),
        "typ": "access",
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "username": user.username,
        "musician_id": user.musician_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(8),
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALG)
    return token, ACCESS_TOKEN_MINUTES * 60


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        _jwt_secret(),
        algorithms=[JWT_ALG],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
        options={"require": ["exp", "sub", "typ"]},
    )


def issue_refresh_token(
    db: Session,
    user: User,
    *,
    client: str | None = None,
    user_agent: str | None = None,
) -> str:
    raw = secrets.token_urlsafe(48)
    row = ApiRefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS),
        client=(client or "")[:40] or None,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(row)
    db.commit()
    return raw


def rotate_refresh_token(
    db: Session,
    raw_refresh: str,
    *,
    client: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, str] | None:
    """Valida refresh, revoga o antigo e emite um novo (rotação)."""
    th = hash_token(raw_refresh)
    row = db.query(ApiRefreshToken).filter(ApiRefreshToken.token_hash == th).first()
    if not row or row.revoked_at is not None:
        return None
    now = datetime.now(timezone.utc)
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if now > exp:
        return None
    user = db.query(User).filter(User.id == row.user_id).first()
    if not user or not user.is_active:
        return None

    row.revoked_at = now
    db.commit()
    new_raw = issue_refresh_token(db, user, client=client or row.client, user_agent=user_agent)
    return user, new_raw


def revoke_refresh_token(db: Session, raw_refresh: str) -> bool:
    th = hash_token(raw_refresh)
    row = db.query(ApiRefreshToken).filter(ApiRefreshToken.token_hash == th).first()
    if not row or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return True


def revoke_all_user_tokens(db: Session, user_id: int) -> int:
    now = datetime.now(timezone.utc)
    q = (
        db.query(ApiRefreshToken)
        .filter(ApiRefreshToken.user_id == user_id, ApiRefreshToken.revoked_at.is_(None))
    )
    n = q.count()
    q.update({"revoked_at": now}, synchronize_session=False)
    db.commit()
    return n
