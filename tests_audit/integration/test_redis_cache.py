"""
Integration tests — Redis cache-aside pattern for footer_config.
Uses fakeredis (in-memory) to avoid a real Redis connection.

Install: pip install fakeredis
"""
import json
import pytest
from unittest.mock import MagicMock, patch, call

# Import the internal helpers directly — they accept an explicit redis client
from app.routers.settings import (
    _cache_get_footer,
    _cache_set_footer,
    _cache_del_footer,
    _get_footer_config,
    _FOOTER_CACHE_KEY,
    _FOOTER_CACHE_TTL,
)

try:
    import fakeredis
    HAS_FAKEREDIS = True
except ImportError:
    HAS_FAKEREDIS = False

pytestmark = pytest.mark.skipif(not HAS_FAKEREDIS, reason="fakeredis not installed")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_redis():
    """In-memory Redis compatible with the app's redis.Redis interface."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def sample_footer():
    return {
        "nome_institucional": "Orquestra",
        "endereco": "Rua das Cordas, 42",
        "link_estatuto": "https://example.org/estatuto",
        "link_repositorio": "https://github.com/example",
    }


# ---------------------------------------------------------------------------
# _cache_get_footer
# ---------------------------------------------------------------------------

class TestCacheGetFooter:
    def test_cache_miss_returns_none(self, fake_redis):
        result = _cache_get_footer(fake_redis)
        assert result is None

    def test_cache_hit_returns_parsed_dict(self, fake_redis, sample_footer):
        fake_redis.set(_FOOTER_CACHE_KEY, json.dumps(sample_footer))
        result = _cache_get_footer(fake_redis)
        assert result == sample_footer

    def test_none_redis_returns_none(self):
        result = _cache_get_footer(None)
        assert result is None

    def test_redis_connection_error_returns_none(self):
        r = MagicMock()
        r.get.side_effect = ConnectionError("Redis unreachable")
        result = _cache_get_footer(r)
        assert result is None

    def test_corrupt_json_returns_none(self, fake_redis):
        fake_redis.set(_FOOTER_CACHE_KEY, "not-valid-json{{{")
        result = _cache_get_footer(fake_redis)
        assert result is None


# ---------------------------------------------------------------------------
# _cache_set_footer
# ---------------------------------------------------------------------------

class TestCacheSetFooter:
    def test_sets_key_with_correct_ttl(self, fake_redis, sample_footer):
        _cache_set_footer(fake_redis, sample_footer)
        raw = fake_redis.get(_FOOTER_CACHE_KEY)
        assert raw is not None
        assert json.loads(raw) == sample_footer
        # TTL should be close to _FOOTER_CACHE_TTL
        ttl = fake_redis.ttl(_FOOTER_CACHE_KEY)
        assert 0 < ttl <= _FOOTER_CACHE_TTL

    def test_none_redis_does_not_raise(self):
        _cache_set_footer(None, {"key": "value"})  # must not raise

    def test_redis_error_does_not_raise(self):
        r = MagicMock()
        r.setex.side_effect = ConnectionError("Redis down")
        _cache_set_footer(r, {"key": "value"})  # must not raise


# ---------------------------------------------------------------------------
# _cache_del_footer
# ---------------------------------------------------------------------------

class TestCacheDelFooter:
    def test_deletes_existing_key(self, fake_redis, sample_footer):
        fake_redis.set(_FOOTER_CACHE_KEY, json.dumps(sample_footer))
        _cache_del_footer(fake_redis)
        assert fake_redis.get(_FOOTER_CACHE_KEY) is None

    def test_delete_missing_key_does_not_raise(self, fake_redis):
        _cache_del_footer(fake_redis)  # key doesn't exist — must not raise

    def test_none_redis_does_not_raise(self):
        _cache_del_footer(None)

    def test_redis_error_does_not_raise(self):
        r = MagicMock()
        r.delete.side_effect = ConnectionError("Redis down")
        _cache_del_footer(r)  # must not raise


# ---------------------------------------------------------------------------
# _get_footer_config — full cache-aside flow
# ---------------------------------------------------------------------------

class TestGetFooterConfigCacheAside:
    def _make_request(self, redis_client):
        """Build a minimal mock request with app.state.redis set."""
        request = MagicMock()
        request.app.state.redis = redis_client
        return request

    def _make_db_with_config(self, footer: dict):
        """Build a mock DB session that returns a Configuracao-like object."""
        cfg = MagicMock()
        cfg.to_dict.return_value = footer
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = cfg
        return db

    def test_cache_miss_populates_cache(self, fake_redis, sample_footer):
        request = self._make_request(fake_redis)
        db = self._make_db_with_config(sample_footer)

        result = _get_footer_config(request, db)

        assert result == sample_footer
        # DB was queried
        db.query.assert_called_once()
        # Cache is now populated
        assert _cache_get_footer(fake_redis) == sample_footer

    def test_cache_hit_skips_db(self, fake_redis, sample_footer):
        fake_redis.set(_FOOTER_CACHE_KEY, json.dumps(sample_footer))
        request = self._make_request(fake_redis)
        db = MagicMock()

        result = _get_footer_config(request, db)

        assert result == sample_footer
        db.query.assert_not_called()

    def test_redis_down_falls_back_to_db(self, sample_footer):
        """Redis unavailable → app falls back to DB, no exception raised."""
        r = MagicMock()
        r.get.side_effect = ConnectionError("Redis down")
        request = self._make_request(r)
        db = self._make_db_with_config(sample_footer)

        result = _get_footer_config(request, db)

        assert result == sample_footer
        db.query.assert_called_once()

    def test_no_redis_configured_falls_back_to_db(self, sample_footer):
        """app.state.redis is None → DB used directly."""
        request = MagicMock()
        request.app.state.redis = None
        db = self._make_db_with_config(sample_footer)

        result = _get_footer_config(request, db)
        assert result == sample_footer
