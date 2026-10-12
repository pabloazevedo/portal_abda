"""
Unit tests — computed properties on SQLAlchemy models and phone validators.
No DB session required: objects are constructed directly in memory.
"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from app.models import (
    Musician, Patrimonio, PatrimonioEmprestimo,
    MemberRole, RoleType, VoiceType,
    StatusPatrimonio, TipoItem,
)
from app.routers.musicians import validate_celular, validate_telefone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_musician(first="João", last="Silva", birth_date=date(1996, 5, 10), roles=None, instruments=None):
    m = Musician()
    m.first_name = first
    m.last_name = last
    m.birth_date = birth_date
    m.roles = roles or []
    m.instruments = instruments or []
    return m


def make_patrimonio(status=StatusPatrimonio.Disponivel, emprestimos=None):
    p = Patrimonio()
    p.tipo_item = TipoItem.Instrumento
    p.status = status
    p.identificador_interno = "INS-202605-0001"
    p.emprestimos = emprestimos or []
    return p


def make_emprestimo(devolvido=False):
    e = PatrimonioEmprestimo()
    e.data_devolucao = datetime.now() if devolvido else None
    e.musician_id = 1
    return e


# ---------------------------------------------------------------------------
# Musician.full_name
# ---------------------------------------------------------------------------

class TestMusicianFullName:
    def test_full_name_returns_first_and_last(self):
        m = make_musician("João", "Silva")
        assert m.full_name == "João Silva"

    def test_full_name_with_compound_last_name(self):
        m = make_musician("Maria", "Santos Oliveira")
        assert m.full_name == "Maria Santos Oliveira"

    def test_full_name_empty_last(self):
        m = make_musician("João", "")
        assert m.full_name == "João "  # property concatenates with space — keep as-is

    def test_full_name_unicode(self):
        m = make_musician("André", "Gonçalves")
        assert m.full_name == "André Gonçalves"


# ---------------------------------------------------------------------------
# Musician.age — uses datetime.today() internally; patch for determinism
# ---------------------------------------------------------------------------

class TestMusicianAge:
    def _age(self, birth_date: date, today: date) -> int:
        m = make_musician(birth_date=birth_date)
        with patch("app.models.datetime") as mock_dt:
            mock_dt.today.return_value = datetime(today.year, today.month, today.day)
            return m.age

    def test_age_exact_birthday_today(self):
        today = date(2026, 5, 10)
        age = self._age(birth_date=date(1996, 5, 10), today=today)
        assert age == 30

    def test_age_birthday_not_yet_this_year(self):
        today = date(2026, 5, 10)
        # Birthday is May 15 — not yet happened
        age = self._age(birth_date=date(1996, 5, 15), today=today)
        assert age == 29

    def test_age_birthday_already_passed_this_year(self):
        today = date(2026, 5, 10)
        # Birthday is April 1
        age = self._age(birth_date=date(1996, 4, 1), today=today)
        assert age == 30

    def test_age_born_today_same_year_would_be_zero(self):
        today = date(2026, 5, 10)
        age = self._age(birth_date=date(2026, 5, 10), today=today)
        assert age == 0

    def test_age_leap_year_born_feb29(self):
        today = date(2026, 3, 1)
        # Born Feb 29, 2000 — 2026 is not a leap year
        age = self._age(birth_date=date(2000, 2, 29), today=today)
        assert age == 26


# ---------------------------------------------------------------------------
# Musician.role_labels
# ---------------------------------------------------------------------------

class TestMusicianRoleLabels:
    def test_no_roles_returns_empty_list(self):
        m = make_musician(roles=[])
        assert m.role_labels == []

    def test_musico_label(self):
        role = MemberRole()
        role.role_type = RoleType.musico
        role.maestro_order = None
        role.voice_type = None
        m = make_musician(roles=[role])
        assert "Músico" in m.role_labels

    def test_maestro_label_with_order(self):
        role = MemberRole()
        role.role_type = RoleType.maestro
        role.maestro_order = 1
        role.voice_type = None
        m = make_musician(roles=[role])
        assert "1º Maestro/Maestrina" in m.role_labels

    def test_maestro_label_without_order(self):
        role = MemberRole()
        role.role_type = RoleType.maestro
        role.maestro_order = None
        role.voice_type = None
        m = make_musician(roles=[role])
        assert "Maestro/Maestrina" in m.role_labels

    def test_cantor_label_with_voice(self):
        role = MemberRole()
        role.role_type = RoleType.cantor
        role.voice_type = VoiceType.soprano
        role.maestro_order = None
        m = make_musician(roles=[role])
        assert "Coralista (Soprano)" in m.role_labels

    def test_multiple_roles(self):
        r1 = MemberRole()
        r1.role_type = RoleType.musico
        r1.maestro_order = None
        r1.voice_type = None

        r2 = MemberRole()
        r2.role_type = RoleType.arranjador
        r2.maestro_order = None
        r2.voice_type = None

        m = make_musician(roles=[r1, r2])
        assert len(m.role_labels) == 2


# ---------------------------------------------------------------------------
# Musician.instrument_names
# ---------------------------------------------------------------------------

class TestMusicianInstrumentNames:
    def test_no_instruments_returns_empty(self):
        m = make_musician(instruments=[])
        assert m.instrument_names == []

    def test_single_instrument_name(self):
        inst = MagicMock()
        inst.nome = "Violino"
        m = make_musician(instruments=[inst])
        assert m.instrument_names == ["Violino"]

    def test_multiple_instruments(self):
        violino = MagicMock()
        violino.nome = "Violino"
        flauta = MagicMock()
        flauta.nome = "Flauta"
        m = make_musician(instruments=[violino, flauta])
        assert set(m.instrument_names) == {"Violino", "Flauta"}


# ---------------------------------------------------------------------------
# Patrimonio.emprestimo_ativo
# ---------------------------------------------------------------------------

class TestPatrimonioEmprestimoAtivo:
    def test_no_emprestimos_returns_none(self):
        p = make_patrimonio(emprestimos=[])
        assert p.emprestimo_ativo is None

    def test_all_emprestimos_devolvidos_returns_none(self):
        e1 = make_emprestimo(devolvido=True)
        e2 = make_emprestimo(devolvido=True)
        p = make_patrimonio(emprestimos=[e1, e2])
        assert p.emprestimo_ativo is None

    def test_one_open_emprestimo_returned(self):
        e_open = make_emprestimo(devolvido=False)
        p = make_patrimonio(emprestimos=[e_open])
        assert p.emprestimo_ativo is e_open

    def test_mixed_returns_open_one(self):
        e_closed = make_emprestimo(devolvido=True)
        e_open = make_emprestimo(devolvido=False)
        p = make_patrimonio(emprestimos=[e_closed, e_open])
        assert p.emprestimo_ativo is e_open

    def test_double_open_returns_first(self):
        """Invariant: only one open emprestimo should exist, but property returns first found."""
        e1 = make_emprestimo(devolvido=False)
        e2 = make_emprestimo(devolvido=False)
        p = make_patrimonio(emprestimos=[e1, e2])
        assert p.emprestimo_ativo is e1


# ---------------------------------------------------------------------------
# Musician.apelido — optional nickname field
# ---------------------------------------------------------------------------

class TestMusicianApelido:
    def test_apelido_defaults_to_none(self):
        m = make_musician()
        assert m.apelido is None

    def test_apelido_stored_correctly(self):
        m = make_musician()
        m.apelido = "Maestro João"
        assert m.apelido == "Maestro João"

    def test_apelido_unicode(self):
        m = make_musician()
        m.apelido = "Zé Viola"
        assert m.apelido == "Zé Viola"

    def test_apelido_none_does_not_affect_full_name(self):
        m = make_musician("Carlos", "Souza")
        m.apelido = None
        assert m.full_name == "Carlos Souza"


# ---------------------------------------------------------------------------
# validate_celular / validate_telefone — phone validators (regression)
# ---------------------------------------------------------------------------

class TestValidateCelular:
    def test_valid_celular(self):
        ok, _ = validate_celular("11987654321")
        assert ok is True

    def test_valid_celular_with_mask(self):
        ok, _ = validate_celular("(11) 98765-4321")
        assert ok is True

    def test_invalid_too_short(self):
        ok, msg = validate_celular("1198765432")
        assert ok is False
        assert "11" in msg

    def test_invalid_no_9_after_ddd(self):
        ok, msg = validate_celular("11887654321")
        assert ok is False
        assert "9" in msg

    def test_invalid_empty(self):
        ok, _ = validate_celular("")
        assert ok is False


class TestValidateTelefone:
    def test_empty_is_valid(self):
        ok, _ = validate_telefone("")
        assert ok is True

    def test_none_string_is_invalid(self):
        """Regression: 'None' string from unguarded template must fail validation."""
        ok, msg = validate_telefone("None")
        assert ok is False

    def test_valid_telefone(self):
        ok, _ = validate_telefone("1133334444")
        assert ok is True

    def test_valid_telefone_with_mask(self):
        ok, _ = validate_telefone("(11) 3333-4444")
        assert ok is True

    def test_invalid_11_digits_is_rejected(self):
        ok, msg = validate_telefone("11987654321")
        assert ok is False

    def test_whitespace_only_is_valid(self):
        ok, _ = validate_telefone("   ")
        assert ok is True
