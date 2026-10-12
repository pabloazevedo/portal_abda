"""Testes da API mobile v1 (auth + partituras + proteção uploads)."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("httpx")

from app.main import app
from app.database import SessionLocal
from app.models import User, UserRole, Musician
from app.mobile_auth import create_access_token
import bcrypt


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def _ensure_musician_user(db, username="musico_app", password="secret12"):
    m = db.query(Musician).filter(Musician.email == f"{username}@test.local").first()
    if not m:
        m = Musician(
            first_name="App",
            last_name="Musico",
            email=f"{username}@test.local",
            celular="11999999999",
            birth_date=date(1990, 1, 15),
            is_active=True,
        )
        db.add(m)
        db.commit()
        db.refresh(m)

    u = db.query(User).filter(User.username == username).first()
    if not u:
        u = User(
            username=username,
            email=f"{username}@test.local",
            password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            role=UserRole.user,
            is_active=True,
            musician_id=m.id,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    else:
        u.musician_id = m.id
        u.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        u.is_active = True
        db.commit()
        db.refresh(u)
    return u, m, password


def _ensure_user_without_musician(db, username="app_no_link", password="secret12"):
    u = db.query(User).filter(User.username == username).first()
    if not u:
        u = User(
            username=username,
            email=f"{username}@test.local",
            password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            role=UserRole.user,
            is_active=True,
            musician_id=None,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    else:
        u.musician_id = None
        u.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        u.is_active = True
        db.commit()
        db.refresh(u)
    return u, password


def test_openapi_available(client):
    r = client.get("/api/openapi.json")
    assert r.status_code == 200
    assert "/api/v1/auth/login" in r.text or "auth/login" in r.text


def test_api_login_and_me(client, db):
    user, m, password = _ensure_musician_user(db)
    r = client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": password, "client": "android"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["token_type"] == "Bearer"
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["user"]["musician_id"] == m.id

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200
    assert me.json()["musician_id"] == m.id


def test_api_login_wrong_password(client, db):
    user, _, _ = _ensure_musician_user(db, username="musico_bad")
    r = client.post("/api/v1/auth/login", json={"username": user.username, "password": "wrongpass"})
    assert r.status_code == 401


def test_api_refresh_rotates(client, db):
    user, _, password = _ensure_musician_user(db, username="musico_refresh")
    login = client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": password, "client": "ios"},
    )
    assert login.status_code == 200, login.text
    old_refresh = login.json()["refresh_token"]

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh, "client": "ios"})
    assert refreshed.status_code == 200, refreshed.text
    new_refresh = refreshed.json()["refresh_token"]
    assert new_refresh != old_refresh

    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401


def test_partituras_requires_musician_link(client, db):
    u, _ = _ensure_user_without_musician(db)
    assert u.musician_id is None
    token, _ = create_access_token(u)
    r = client.get("/api/v1/me/partituras", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403, r.text
    assert "vínculo" in r.text.lower() or "vinculo" in r.text.lower() or "membro" in r.text.lower()


def test_partituras_list_empty_ok(client, db):
    user, _, password = _ensure_musician_user(db, username="musico_empty")
    login = client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": password, "client": "android"},
    )
    assert login.status_code == 200
    r = client.get(
        "/api/v1/me/partituras",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["musician_id"] == user.musician_id
    assert body["count"] == 0
    assert body["items"] == []
    assert "server_time" in body


def test_uploads_obras_blocked_without_session(client):
    r = client.get("/uploads/obras/does-not-exist/x.pdf")
    assert r.status_code == 401


def test_healthz_still_public(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200
