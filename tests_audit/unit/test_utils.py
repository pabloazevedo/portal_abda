"""
Unit tests — app/utils.py: detect_image_type() magic byte detection.
No I/O, no DB, no network.
"""
import pytest
from app.utils import detect_image_type


# ---------------------------------------------------------------------------
# Valid image headers
# ---------------------------------------------------------------------------

JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG_HEADER  = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
GIF87_HEADER = b"GIF87a" + b"\x00" * 100
GIF89_HEADER = b"GIF89a" + b"\x00" * 100
WEBP_HEADER  = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 100

# Invalid / unsupported
PDF_HEADER  = b"%PDF-1.4" + b"\x00" * 100
EXE_HEADER  = b"MZ" + b"\x00" * 100
EMPTY       = b""
TOO_SHORT   = b"\xff\xd8"  # Only 2 bytes — too short for any complete signature


class TestDetectImageTypeValid:
    def test_detects_jpeg(self):
        assert detect_image_type(JPEG_HEADER) == ".jpg"

    def test_detects_png(self):
        assert detect_image_type(PNG_HEADER) == ".png"

    def test_detects_gif87(self):
        assert detect_image_type(GIF87_HEADER) == ".gif"

    def test_detects_gif89(self):
        assert detect_image_type(GIF89_HEADER) == ".gif"

    def test_detects_webp(self):
        assert detect_image_type(WEBP_HEADER) == ".webp"


class TestDetectImageTypeInvalid:
    def test_pdf_not_detected(self):
        assert detect_image_type(PDF_HEADER) is None

    def test_exe_not_detected(self):
        assert detect_image_type(EXE_HEADER) is None

    def test_empty_bytes_not_detected(self):
        assert detect_image_type(EMPTY) is None

    def test_too_short_not_detected(self):
        assert detect_image_type(TOO_SHORT) is None

    def test_random_bytes_not_detected(self):
        assert detect_image_type(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08") is None


class TestDetectImageTypeWebPVariant:
    def test_riff_without_webp_marker_returns_none(self):
        """RIFF header without WEBP at bytes 8-12 must not match."""
        fake_riff = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 100
        assert detect_image_type(fake_riff) is None

    def test_webp_with_correct_subtype(self):
        assert detect_image_type(WEBP_HEADER) == ".webp"


class TestDetectImageTypeSecurity:
    def test_jpeg_extension_on_png_content_detects_png(self):
        """Extension is never used; only content determines type."""
        assert detect_image_type(PNG_HEADER) == ".png"

    def test_polyglot_jpeg_png_prefers_jpeg_if_jpeg_first(self):
        """If bytes start with JPEG magic, return JPEG regardless of trailing content."""
        polyglot = JPEG_HEADER[:4] + PNG_HEADER[4:]
        assert detect_image_type(polyglot) == ".jpg"
