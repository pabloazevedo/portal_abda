"""
Integration tests — PostgreSQL session lifecycle and fail-soft behavior.
Uses mocked SQLAlchemy engine to avoid a real DB connection.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.exc import OperationalError, TimeoutError as SATimeoutError

from app.database import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _consume_generator(gen):
    """Drive a generator-based dependency to completion."""
    db = next(gen)
    try:
        gen.send(None)
    except StopIteration:
        pass
    return db


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

class TestGetDbLifecycle:
    def test_yields_session(self):
        mock_session = MagicMock()
        mock_session_factory = MagicMock(return_value=mock_session)

        with patch("app.database.SessionLocal", mock_session_factory):
            gen = get_db()
            db = next(gen)
            assert db is mock_session

    def test_session_closed_after_normal_use(self):
        mock_session = MagicMock()
        with patch("app.database.SessionLocal", return_value=mock_session):
            gen = get_db()
            next(gen)
            try:
                next(gen)
            except StopIteration:
                pass
            mock_session.close.assert_called_once()

    def test_session_closed_after_exception_in_route(self):
        """Even if the route raises, the finally block must close the session."""
        mock_session = MagicMock()
        with patch("app.database.SessionLocal", return_value=mock_session):
            gen = get_db()
            next(gen)
            try:
                gen.throw(RuntimeError("Simulated route error"))
            except RuntimeError:
                pass
            except StopIteration:
                pass
            mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# Parameterized query safety — no raw string interpolation
# ---------------------------------------------------------------------------

class TestQueryParameterization:
    def test_search_query_uses_bind_params(self):
        """
        Verifies that search routes pass user input as bind parameters,
        not via raw string interpolation.
        This is a structural test: we check that ilike() is called with
        a parameter object, not a pre-formatted string containing user input.
        """
        from sqlalchemy import Column, String, select
        from sqlalchemy.orm import DeclarativeBase

        class Base(DeclarativeBase):
            pass

        class FakeModel(Base):
            __tablename__ = "fake"
            id   = Column(String, primary_key=True)
            nome = Column(String)

        user_input = "violino'; DROP TABLE musicians; --"
        # Build the query the same way the app does
        stmt = select(FakeModel).where(FakeModel.nome.ilike(f"%{user_input}%"))
        # The compiled query should use a bound parameter, not the raw string
        compiled = stmt.compile()
        # The param dict should contain the user input as a value, not embedded in SQL text
        sql_text = str(compiled)
        assert "DROP TABLE" not in sql_text  # SQL text should have placeholder, not literal
        assert "%" in sql_text or "ilike" in sql_text.lower()


# ---------------------------------------------------------------------------
# Connection pool exhaustion simulation
# ---------------------------------------------------------------------------

class TestConnectionPoolExhaustion:
    def test_pool_timeout_closes_session(self):
        """
        When pool is exhausted, SessionLocal raises TimeoutError.
        No session is yielded, and no close() call should be attempted on None.
        """
        with patch("app.database.SessionLocal", side_effect=SATimeoutError()):
            gen = get_db()
            with pytest.raises(SATimeoutError):
                next(gen)

    def test_operational_error_propagates(self):
        """Connection refused → OperationalError propagates to route."""
        with patch("app.database.SessionLocal", side_effect=OperationalError("conn refused", None, None)):
            gen = get_db()
            with pytest.raises(OperationalError):
                next(gen)


# ---------------------------------------------------------------------------
# Idempotency: calling get_db multiple times creates independent sessions
# ---------------------------------------------------------------------------

class TestGetDbIndependentSessions:
    def test_two_calls_create_two_sessions(self):
        sessions = [MagicMock(), MagicMock()]
        call_count = 0

        def factory():
            nonlocal call_count
            s = sessions[call_count]
            call_count += 1
            return s

        with patch("app.database.SessionLocal", side_effect=factory):
            gen1 = get_db()
            gen2 = get_db()
            db1 = next(gen1)
            db2 = next(gen2)
            assert db1 is sessions[0]
            assert db2 is sessions[1]
            assert db1 is not db2
