"""
Portal — Utilitários compartilhados (D-02).
Magic bytes para validação de imagens, usados em musicians.py e settings.py.
"""

from typing import Optional

# Assinaturas binárias suportadas para upload de imagens
MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff",        ".jpg"),   # JPEG
    (b"\x89PNG\r\n\x1a\n",  ".png"),   # PNG
    (b"GIF87a",              ".gif"),   # GIF87
    (b"GIF89a",              ".gif"),   # GIF89
    (b"RIFF",                ".webp"),  # WebP (verificação parcial)
]


def detect_image_type(data: bytes) -> Optional[str]:
    """Retorna a extensão detectada pelo conteúdo binário, ou None se não reconhecido."""
    for magic, ext in MAGIC_SIGNATURES:
        if data[: len(magic)] == magic:
            if ext == ".webp":
                return ext if data[8:12] == b"WEBP" else None
            return ext
    return None
