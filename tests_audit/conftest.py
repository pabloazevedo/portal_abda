"""
Shared fixtures for the audit test suite.
All external dependencies (DB, Redis, SMTP) are mocked by default.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import date, datetime, timedelta


# ---------------------------------------------------------------------------
# User / session helpers
# ---------------------------------------------------------------------------

def make_user(role: str = "user", user_id: int = 1, username: str = "testuser") -> dict:
    """Return a session dict matching request.session['user'] format."""
    return {"id": user_id, "username": username, "email": f"{username}@test.com", "role": role}


@pytest.fixture
def user_admin():
    return make_user(role="admin", user_id=1, username="admin")


@pytest.fixture
def user_maestro():
    return make_user(role="maestro", user_id=2, username="maestro1")


@pytest.fixture
def user_arquivista():
    return make_user(role="arquivista", user_id=3, username="arquivista1")


@pytest.fixture
def user_secretaria():
    return make_user(role="secretaria", user_id=4, username="secretaria1")


@pytest.fixture
def user_regular():
    return make_user(role="user", user_id=5, username="musician1")


# ---------------------------------------------------------------------------
# Mock DB session
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """SQLAlchemy session mock that supports common query patterns."""
    db = MagicMock()
    db.exec = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.delete = MagicMock()
    db.rollback = MagicMock()
    db.close = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Mock Redis client
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    """Redis client mock with basic get/set/delete/setex/ping."""
    r = MagicMock()
    r.get = MagicMock(return_value=None)
    r.set = MagicMock(return_value=True)
    r.setex = MagicMock(return_value=True)
    r.delete = MagicMock(return_value=1)
    r.ping = MagicMock(return_value=True)
    return r


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def fixed_today():
    return date(2026, 5, 10)


@pytest.fixture
def birth_date_30y():
    return date(1996, 5, 10)


@pytest.fixture
def birth_date_no_birthday_yet():
    """Birthday is May 15 — has not occurred yet as of 2026-05-10."""
    return date(1996, 5, 15)
