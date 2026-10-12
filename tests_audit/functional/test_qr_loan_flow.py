"""
Functional tests — QR Code instrument loan flow end-to-end.

Tests the full flow:
  scan tag → resolve item → lend → return

Uses FastAPI TestClient with mocked DB (no real Postgres required).
Requires: pip install httpx pytest-mock
"""
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.models import (
    Patrimonio, PatrimonioEtiqueta, PatrimonioEmprestimo, PatrimonioAuditoria,
    Musician, EtiquetaTipo, StatusPatrimonio, TipoItem,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ITEM_UUID = uuid.uuid4()
MUSICIAN_ID = 7
EMPRESTIMO_ID = 42
QR_VALOR = "QR-TEST-ABC123"


def make_item(status=StatusPatrimonio.Disponivel, emprestimos=None):
    item = MagicMock(spec=Patrimonio)
    item.id = ITEM_UUID
    item.identificador_interno = "INS-202605-0001"
    item.tipo_item = TipoItem.Instrumento
    item.status = status
    item.fabricante = "Yamaha"
    item.modelo = "V5"
    item.ano_compra = 2020
    item.detalhes = {}
    item.observacoes = None
    item.emprestimos = emprestimos or []
    item.emprestimo_ativo = None if not emprestimos else next(
        (e for e in emprestimos if e.data_devolucao is None), None
    )
    return item


def make_etiqueta(valor=QR_VALOR, item_id=ITEM_UUID):
    e = MagicMock(spec=PatrimonioEtiqueta)
    e.tipo = EtiquetaTipo.qr
    e.valor = valor
    e.patrimonio_id = item_id
    e.ativo = True
    return e


def make_musician():
    m = MagicMock(spec=Musician)
    m.id = MUSICIAN_ID
    m.first_name = "Carlos"
    m.last_name = "Drummond"
    m.full_name = "Carlos Drummond"
    m.is_active = True
    return m


def make_emprestimo(devolvido=False):
    e = MagicMock(spec=PatrimonioEmprestimo)
    e.id = EMPRESTIMO_ID
    e.patrimonio_id = ITEM_UUID
    e.musician_id = MUSICIAN_ID
    e.data_emprestimo = datetime(2026, 5, 10, 9, 0, tzinfo=timezone.utc)
    e.data_devolucao = datetime(2026, 5, 10, 18, 0, tzinfo=timezone.utc) if devolvido else None
    e.musician = make_musician()
    return e


# ---------------------------------------------------------------------------
# Test client with session patching
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_session(request_mark=None):
    """
    Returns a TestClient where session["user"] is pre-set to an arquivista.
    The DB session is mocked — no real PostgreSQL needed.
    """
    from app.main import app

    # Patch the session middleware to inject a logged-in arquivista user
    with patch("app.main.SessionMiddleware") as _sm:
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ---------------------------------------------------------------------------
# 1. GET /patrimonio/scan/{valor} — tag resolution
# ---------------------------------------------------------------------------

class TestScanTagResolution:
    def test_valid_tag_redirects_to_item(self, mock_db):
        """Known tag → 302 redirect to /patrimonio/{uuid}."""
        etiqueta = make_etiqueta()
        mock_db.query.return_value.filter.return_value.first.return_value = etiqueta

        from app.routers.patrimonio import scan_redirect
        import asyncio

        request = MagicMock()
        request.app.state = MagicMock()
        result = asyncio.get_event_loop().run_until_complete(
            scan_redirect(QR_VALOR, request, mock_db)
        )
        assert result.status_code == 302
        assert str(ITEM_UUID) in result.headers["location"]

    def test_unknown_tag_returns_404(self, mock_db):
        """Unknown tag → HTTPException 404."""
        from fastapi import HTTPException
        from app.routers.patrimonio import scan_redirect
        import asyncio

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                scan_redirect("INVALID_TAG_XYZ", MagicMock(), mock_db)
            )
        assert exc_info.value.status_code == 404

    def test_inactive_tag_not_resolved(self, mock_db):
        """Inactive tag (ativo=False) should not match — simulate by returning None."""
        from fastapi import HTTPException
        from app.routers.patrimonio import scan_redirect
        import asyncio

        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                scan_redirect(QR_VALOR, MagicMock(), mock_db)
            )
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 2. GET /patrimonio/qr/{identificador} — JSON detail
# ---------------------------------------------------------------------------

class TestQrDetailJson:
    def test_available_item_returns_correct_json(self, mock_db):
        item = make_item(status=StatusPatrimonio.Disponivel)
        item.emprestimo_ativo = None
        mock_db.query.return_value.filter.return_value.first.return_value = item

        from app.routers.patrimonio import qr_detail_json
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            qr_detail_json("INS-202605-0001", mock_db)
        )
        body = result.body
        import json
        data = json.loads(body)
        assert data["identificador_interno"] == "INS-202605-0001"
        assert data["musico_responsavel"] is None
        assert data["data_emprestimo"] is None

    def test_borrowed_item_includes_musician_name(self, mock_db):
        emp = make_emprestimo(devolvido=False)
        item = make_item(status=StatusPatrimonio.Emprestado, emprestimos=[emp])
        item.emprestimo_ativo = emp
        mock_db.query.return_value.filter.return_value.first.return_value = item

        from app.routers.patrimonio import qr_detail_json
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            qr_detail_json("INS-202605-0001", mock_db)
        )
        import json
        data = json.loads(result.body)
        assert data["musico_responsavel"] == "Carlos Drummond"
        assert data["data_emprestimo"] is not None

    def test_unknown_item_returns_404(self, mock_db):
        from fastapi import HTTPException
        from app.routers.patrimonio import qr_detail_json
        import asyncio

        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                qr_detail_json("INS-XXXX-9999", mock_db)
            )
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 3. POST /patrimonio/{id}/vincular — loan creation
# ---------------------------------------------------------------------------

class TestVincularPatrimonio:
    def _run_vincular(self, mock_db, item, musician):
        from app.routers.patrimonio import vincular_patrimonio
        import asyncio

        request = MagicMock()
        request.app.state = MagicMock()
        request.session = {"user": {"id": 3, "role": "arquivista"}}

        db_responses = iter([item, musician])
        mock_db.query.return_value.filter.return_value.first.side_effect = lambda: next(db_responses, None)

        user_ctx = {"id": 3, "role": "arquivista"}
        return asyncio.get_event_loop().run_until_complete(
            vincular_patrimonio(ITEM_UUID, request, mock_db, user_ctx, MUSICIAN_ID, "")
        )

    def test_available_item_gets_borrowed(self, mock_db):
        item = make_item(status=StatusPatrimonio.Disponivel)
        musician = make_musician()
        result = self._run_vincular(mock_db, item, musician)
        assert result.status_code == 303
        assert item.status == StatusPatrimonio.Emprestado
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_already_borrowed_item_redirects_with_error(self, mock_db):
        item = make_item(status=StatusPatrimonio.Emprestado)
        musician = make_musician()
        result = self._run_vincular(mock_db, item, musician)
        assert result.status_code == 303
        assert "erro" in result.headers["location"]
        # No new emprestimo should be created
        mock_db.add.assert_not_called()

    def test_baixa_item_cannot_be_lent(self, mock_db):
        item = make_item(status=StatusPatrimonio.Baixa)
        musician = make_musician()
        result = self._run_vincular(mock_db, item, musician)
        assert result.status_code == 303
        assert "erro" in result.headers["location"]

    def test_nonexistent_musician_raises_404(self, mock_db):
        from fastapi import HTTPException
        from app.routers.patrimonio import vincular_patrimonio
        import asyncio

        item = make_item(status=StatusPatrimonio.Disponivel)
        request = MagicMock()

        # First query returns item, second returns None (musician not found)
        mock_db.query.return_value.filter.return_value.first.side_effect = [item, None]
        user_ctx = {"id": 3, "role": "arquivista"}

        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                vincular_patrimonio(ITEM_UUID, request, mock_db, user_ctx, 99999, "")
            )
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 4. POST /patrimonio/{id}/desvincular/{emprestimo_id} — return
# ---------------------------------------------------------------------------

class TestDesvincularPatrimonio:
    def test_successful_return_updates_status(self, mock_db):
        from app.routers.patrimonio import desvincular_patrimonio
        import asyncio

        item = make_item(status=StatusPatrimonio.Emprestado)
        emp = make_emprestimo(devolvido=False)
        emp.patrimonio = item

        request = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = emp
        user_ctx = {"id": 3, "role": "arquivista"}

        result = asyncio.get_event_loop().run_until_complete(
            desvincular_patrimonio(ITEM_UUID, EMPRESTIMO_ID, request, mock_db, user_ctx)
        )
        assert result.status_code == 303
        assert emp.data_devolucao is not None
        assert item.status == StatusPatrimonio.Disponivel
        mock_db.commit.assert_called()

    def test_return_without_active_loan_raises_404(self, mock_db):
        from fastapi import HTTPException
        from app.routers.patrimonio import desvincular_patrimonio
        import asyncio

        mock_db.query.return_value.filter.return_value.first.return_value = None
        user_ctx = {"id": 3, "role": "arquivista"}

        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                desvincular_patrimonio(ITEM_UUID, 9999, MagicMock(), mock_db, user_ctx)
            )
        assert exc_info.value.status_code == 404
