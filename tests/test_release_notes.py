"""Testes de versionamento (arquivo VERSION + SemVer helpers)."""
from app.routers.release_notes import normalize_version, validate_version
from app.version import get_version, get_version_uncached, _VERSION_FILE


def test_normalize_version_strips_v_prefix():
    assert normalize_version("v1.2.3") == "1.2.3"
    assert normalize_version("  V2.0.0 ") == "2.0.0"


def test_validate_version_accepts_semver_like():
    assert validate_version("1.0.0") is None
    assert validate_version("1.2.3-beta") is None
    assert validate_version("10.0.1") is None


def test_validate_version_rejects_invalid():
    assert validate_version("") is not None
    assert validate_version("abc") is not None
    assert validate_version("1") is not None


def test_version_file_is_readable_semver():
    assert _VERSION_FILE.exists()
    v = get_version_uncached()
    assert validate_version(v) is None
    assert v == get_version()
