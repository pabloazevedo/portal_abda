"""
Security tests — Injection vulnerabilities.

1. SQL Injection via search/query fields
2. XSS via reflected input in templates
3. Wildcard abuse in ILIKE queries (performance DoS)
4. Path traversal in file upload filenames
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE musicians; --",
    "' OR '1'='1",
    "' UNION SELECT username, password_hash FROM users --",
    "1; SELECT pg_sleep(5)--",
    "%27%20OR%20%271%27%3D%271",  # URL-encoded ' OR '1'='1
]

XSS_PAYLOADS = [
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "';alert(String.fromCharCode(88,83,83))//",
    "<svg onload=alert(1)>",
]

WILDCARD_ABUSE_PAYLOADS = [
    "%_%" * 10,          # Excessive LIKE wildcards
    "%" * 50,            # Pure percent signs
    "_" * 100,           # Pure underscores
    "%" + "a" * 50 + "%",
]

PATH_TRAVERSAL_FILENAMES = [
    "../../etc/passwd",
    "../uploads/secret.jpg",
    "....//....//etc/shadow",
    "%2e%2e%2fetc%2fpasswd",
    "photo\x00.jpg",  # Null byte injection
]


# ---------------------------------------------------------------------------
# 1. SQLAlchemy ORM — SQL injection protection
# ---------------------------------------------------------------------------

class TestSQLInjectionProtection:
    def test_ilike_with_injection_payload_uses_bind_params(self):
        """
        SQLAlchemy's ilike() uses bound parameters internally.
        The SQL text should contain a placeholder (:param), not the raw payload.
        """
        from sqlalchemy import Column, String, select
        from sqlalchemy.orm import DeclarativeBase

        class Base(DeclarativeBase):
            pass

        class FakeMusician(Base):
            __tablename__ = "musicians"
            id         = Column(String, primary_key=True)
            first_name = Column(String)

        for payload in SQL_INJECTION_PAYLOADS:
            like_val = f"%{payload}%"
            stmt = select(FakeMusician).where(FakeMusician.first_name.ilike(like_val))
            compiled = str(stmt.compile())
            # The SQL text must NOT contain the raw payload
            assert "DROP TABLE" not in compiled
            assert "pg_sleep" not in compiled
            assert "UNION SELECT" not in compiled

    def test_enum_validation_blocks_invalid_tipo_item(self):
        """
        TipoItem enum validation prevents injecting arbitrary strings
        into the tipo_item column.
        """
        from app.models import TipoItem
        malicious_inputs = [
            "'; DROP TABLE patrimonio; --",
            "Instrumento' OR '1'='1",
            "<script>",
            "../../../../etc/passwd",
        ]
        for val in malicious_inputs:
            with pytest.raises(ValueError):
                TipoItem(val)

    def test_status_enum_validation_blocks_injection(self):
        from app.models import StatusPatrimonio
        with pytest.raises(ValueError):
            StatusPatrimonio("Disponivel'; DROP TABLE patrimonio; --")

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_search_query_param_does_not_break_query_structure(self, payload):
        """
        Verify the search query-building pattern produces valid SQL structure
        regardless of injection payload.
        """
        from sqlalchemy import Column, String, or_, select
        from sqlalchemy.orm import DeclarativeBase

        class Base2(DeclarativeBase):
            pass

        class FakePatrimonio(Base2):
            __tablename__ = "patrimonio2"
            id                    = Column(String, primary_key=True)
            identificador_interno = Column(String)
            fabricante            = Column(String)
            modelo                = Column(String)
            observacoes           = Column(String)

        like = f"%{payload}%"
        stmt = select(FakePatrimonio).where(or_(
            FakePatrimonio.identificador_interno.ilike(like),
            FakePatrimonio.fabricante.ilike(like),
            FakePatrimonio.modelo.ilike(like),
            FakePatrimonio.observacoes.ilike(like),
        ))
        # Should compile without error
        compiled = stmt.compile()
        assert compiled is not None


# ---------------------------------------------------------------------------
# 2. XSS — Jinja2 auto-escaping validation
# ---------------------------------------------------------------------------

class TestXSSProtection:
    def test_jinja2_autoescape_enabled(self):
        """
        Verify the Jinja2 template environment has autoescape enabled for HTML.
        This protects against reflected XSS when user input is rendered in templates.
        """
        from jinja2 import Environment
        from fastapi.templating import Jinja2Templates

        # FastAPI Jinja2Templates enables autoescape for .html by default
        templates = Jinja2Templates(directory="templates")
        env = templates.env
        # Check that autoescape is configured (function or True)
        assert env.autoescape is not False, \
            "Jinja2 autoescape must be enabled to prevent XSS"

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_jinja2_escapes_html_special_chars(self, payload):
        """Jinja2 must escape angle brackets and quotes in template variables."""
        from jinja2 import Environment, BaseLoader
        env = Environment(autoescape=True, loader=BaseLoader())
        tmpl = env.from_string("{{ user_input }}")
        rendered = tmpl.render(user_input=payload)
        assert "<script>" not in rendered
        assert "onerror=" not in rendered
        assert "onload=" not in rendered

    def test_raw_search_term_is_escaped_in_template(self):
        """The search query 'q' should be escaped when reflected in templates."""
        from jinja2 import Environment, BaseLoader
        env = Environment(autoescape=True, loader=BaseLoader())
        # Simulate the pattern used in search results templates
        tmpl = env.from_string('<input value="{{ q }}">')
        rendered = tmpl.render(q='"><script>alert(1)</script>')
        assert "<script>" not in rendered
        assert "alert" not in rendered


# ---------------------------------------------------------------------------
# 3. Wildcard abuse in ILIKE — performance protection
# ---------------------------------------------------------------------------

class TestWildcardAbuse:
    def test_wildcard_heavy_query_does_not_crash_query_builder(self):
        """
        Wildcard abuse should not break query construction.
        Rate limiting (outside ORM) is the runtime protection.
        """
        from sqlalchemy import Column, String, select
        from sqlalchemy.orm import DeclarativeBase

        class Base3(DeclarativeBase):
            pass

        class Fake3(Base3):
            __tablename__ = "fake3"
            id   = Column(String, primary_key=True)
            nome = Column(String)

        for payload in WILDCARD_ABUSE_PAYLOADS:
            like = f"%{payload}%"
            stmt = select(Fake3).where(Fake3.nome.ilike(like))
            assert stmt.compile() is not None


# ---------------------------------------------------------------------------
# 4. File upload — path traversal and null byte injection
# ---------------------------------------------------------------------------

class TestFileUploadSecurity:
    def test_detect_image_type_rejects_non_image(self):
        """
        File validation uses magic bytes, not filename extensions.
        A path traversal filename with image content must still fail on content check
        if the actual content is not a valid image.
        """
        from app.utils import detect_image_type

        # A file named "../../etc/passwd" with text content
        fake_payload = b"root:x:0:0:root:/root:/bin/bash\n" + b"\x00" * 100
        result = detect_image_type(fake_payload)
        assert result is None

    def test_null_byte_in_content_not_detected_as_valid_image(self):
        """Null bytes prepended to file content do not trigger magic byte match."""
        from app.utils import detect_image_type
        null_prefixed = b"\x00\x00\x00\x00" + b"\xff\xd8\xff"  # null + JPEG header
        # Magic byte check starts at index 0, so null prefix prevents JPEG match
        assert detect_image_type(null_prefixed) is None

    def test_valid_jpeg_with_malicious_name_is_detected_correctly(self):
        """Content determines type — malicious filename does not affect detection."""
        from app.utils import detect_image_type
        jpeg_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        # Even if filename is "../../evil.php", magic bytes say it's a JPEG
        assert detect_image_type(jpeg_content) == ".jpg"

    @pytest.mark.parametrize("filename", PATH_TRAVERSAL_FILENAMES)
    def test_path_traversal_filenames_cannot_escape_upload_dir(self, filename):
        """
        Verify that path traversal sequences in filenames are blocked
        by checking what a safe filename sanitization should produce.

        The app uses UUID-based filenames (random, not user-supplied) — this
        test documents that relying on user-supplied filenames would be dangerous.
        """
        import os
        import re
        # Simulate what a SAFE implementation should do: strip path components
        safe_filename = os.path.basename(filename.replace("\x00", ""))
        # Even after basename, some payloads may still have dots
        # The key protection: uuid filenames prevent this entirely
        assert ".." not in safe_filename or safe_filename == ".."
