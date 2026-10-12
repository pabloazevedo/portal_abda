"""
Unit tests — RBAC helpers in app/dependencies.py.
No DB, no Redis, no network required.
"""
import pytest
from app.dependencies import (
    is_admin, is_maestro, is_arquivista, is_secretaria,
    can_manage_members, can_manage_patrimonio,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def user(role: str) -> dict:
    return {"id": 1, "username": "tester", "email": "t@t.com", "role": role}


# ---------------------------------------------------------------------------
# is_admin
# ---------------------------------------------------------------------------

class TestIsAdmin:
    def test_admin_is_admin(self):
        assert is_admin(user("admin")) is True

    def test_maestro_not_admin(self):
        assert is_admin(user("maestro")) is False

    def test_arquivista_not_admin(self):
        assert is_admin(user("arquivista")) is False

    def test_secretaria_not_admin(self):
        assert is_admin(user("secretaria")) is False

    def test_user_not_admin(self):
        assert is_admin(user("user")) is False

    def test_none_not_admin(self):
        assert is_admin(None) is False

    def test_unknown_role_not_admin(self):
        assert is_admin(user("superuser")) is False


# ---------------------------------------------------------------------------
# is_maestro (admin + maestro)
# ---------------------------------------------------------------------------

class TestIsMaestro:
    def test_maestro_is_maestro(self):
        assert is_maestro(user("maestro")) is True

    def test_admin_is_maestro(self):
        assert is_maestro(user("admin")) is True

    def test_arquivista_not_maestro(self):
        assert is_maestro(user("arquivista")) is False

    def test_secretaria_not_maestro(self):
        assert is_maestro(user("secretaria")) is False

    def test_user_not_maestro(self):
        assert is_maestro(user("user")) is False

    def test_none_not_maestro(self):
        assert is_maestro(None) is False


# ---------------------------------------------------------------------------
# is_arquivista (admin + arquivista)
# ---------------------------------------------------------------------------

class TestIsArquivista:
    def test_arquivista_is_arquivista(self):
        assert is_arquivista(user("arquivista")) is True

    def test_admin_is_arquivista(self):
        assert is_arquivista(user("admin")) is True

    def test_maestro_not_arquivista(self):
        assert is_arquivista(user("maestro")) is False

    def test_user_not_arquivista(self):
        assert is_arquivista(user("user")) is False

    def test_none_not_arquivista(self):
        assert is_arquivista(None) is False


# ---------------------------------------------------------------------------
# is_secretaria (admin + secretaria)
# ---------------------------------------------------------------------------

class TestIsSecretaria:
    def test_secretaria_is_secretaria(self):
        assert is_secretaria(user("secretaria")) is True

    def test_admin_is_secretaria(self):
        assert is_secretaria(user("admin")) is True

    def test_maestro_not_secretaria(self):
        assert is_secretaria(user("maestro")) is False

    def test_user_not_secretaria(self):
        assert is_secretaria(user("user")) is False


# ---------------------------------------------------------------------------
# can_manage_members (admin + maestro + secretaria)
# ---------------------------------------------------------------------------

class TestCanManageMembers:
    @pytest.mark.parametrize("role", ["admin", "maestro", "secretaria"])
    def test_authorized_roles_can_manage_members(self, role):
        assert can_manage_members(user(role)) is True

    @pytest.mark.parametrize("role", ["arquivista", "user"])
    def test_unauthorized_roles_cannot_manage_members(self, role):
        assert can_manage_members(user(role)) is False

    def test_none_cannot_manage_members(self):
        assert can_manage_members(None) is False

    def test_unknown_role_cannot_manage_members(self):
        assert can_manage_members(user("superadmin")) is False


# ---------------------------------------------------------------------------
# can_manage_patrimonio (admin + arquivista)
# ---------------------------------------------------------------------------

class TestCanManagePatrimonio:
    @pytest.mark.parametrize("role", ["admin", "arquivista"])
    def test_authorized_roles_can_manage_patrimonio(self, role):
        assert can_manage_patrimonio(user(role)) is True

    @pytest.mark.parametrize("role", ["maestro", "secretaria", "user"])
    def test_unauthorized_roles_cannot_manage_patrimonio(self, role):
        assert can_manage_patrimonio(user(role)) is False

    def test_none_cannot_manage_patrimonio(self):
        assert can_manage_patrimonio(None) is False


# ---------------------------------------------------------------------------
# Cross-role isolation: secretaria x arquivista are mutually exclusive
# ---------------------------------------------------------------------------

class TestRoleIsolation:
    def test_secretaria_cannot_manage_patrimonio(self):
        assert can_manage_patrimonio(user("secretaria")) is False

    def test_arquivista_cannot_manage_members(self):
        assert can_manage_members(user("arquivista")) is False

    def test_user_cannot_do_anything(self):
        u = user("user")
        assert is_admin(u) is False
        assert is_maestro(u) is False
        assert is_arquivista(u) is False
        assert is_secretaria(u) is False
        assert can_manage_members(u) is False
        assert can_manage_patrimonio(u) is False

    def test_empty_role_string(self):
        u = {"id": 1, "username": "x", "role": ""}
        assert can_manage_members(u) is False
        assert is_admin(u) is False
