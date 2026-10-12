"""
Versão do Orchestra Portal (fonte de verdade no repositório).

SemVer (https://semver.org): MAJOR.MINOR.PATCH
- MAJOR — mudança incompatível (quebra API/comportamento esperado)
- MINOR — funcionalidade nova compatível
- PATCH — correção / ajuste pequeno sem nova feature

O arquivo VERSION na raiz do projeto é lido em runtime e deve ser o mesmo
número usado em tags Git futuras (ex.: v1.1.0) na esteira de CI/CD.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_VERSION_FILE = _ROOT / "VERSION"
_FALLBACK = "0.0.0"


def _read_version_file() -> str | None:
    try:
        raw = _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        return line.lstrip("vV")
    return None


@lru_cache(maxsize=1)
def get_version() -> str:
    """Lê o arquivo VERSION do repositório (fonte de verdade)."""
    return _read_version_file() or _FALLBACK


def get_version_uncached() -> str:
    """Útil em testes / após alterar VERSION sem reiniciar o processo."""
    get_version.cache_clear()
    return get_version()


__version__ = get_version()
