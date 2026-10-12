"""
Portal — Armazenamento unificado de partituras do acervo.
Salva arquivos em disco com estrutura padronizada por obra/arranjo.
"""

import hashlib
import logging
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.constants import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB

logger = logging.getLogger("uvicorn.error")

UPLOADS_ROOT = Path("uploads")
OBRAS_DIR = UPLOADS_ROOT / "obras"


def validar_arquivo_partitura(upload: UploadFile) -> tuple[bytes, str, int]:
    """Valida extensão e tamanho; retorna (bytes, extensão, tamanho)."""
    if not upload.filename:
        raise HTTPException(400, "Nome de arquivo vazio")

    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            422,
            f"Formato não suportado ({ext}). Use: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    file_bytes = upload.file.read()
    upload.file.seek(0)

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(422, f"Arquivo muito grande (máx {MAX_FILE_SIZE_MB}MB)")

    if ext == ".pdf" and not file_bytes.startswith(b"%PDF"):
        raise HTTPException(422, "Arquivo PDF inválido")

    return file_bytes, ext, len(file_bytes)


def _subdir_por_tipo(tipo: str) -> str:
    return {
        "grade": "grade",
        "instrumento": "instrumentos",
        "coral": "coral",
        "acompanhamento": "acompanhamento",
    }.get(tipo, "outros")


def salvar_documento(
    file_bytes: bytes,
    filename: str,
    arranjo_id: int,
    tipo: str,
    instrumento_nome: str | None = None,
) -> tuple[str, int, str]:
    """
    Salva documento no disco.

    Estrutura: uploads/obras/{arranjo_id}/{tipo}/arquivo.pdf

    Retorna: (caminho_relativo, tamanho_bytes, hash_sha256)
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(422, f"Extensão não permitida: {ext}")

    arranjo_dir = OBRAS_DIR / str(arranjo_id) / _subdir_por_tipo(tipo)
    arranjo_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(filename).stem.replace(" ", "_")
    if instrumento_nome and tipo == "instrumento":
        safe_inst = instrumento_nome.replace(" ", "_").replace("/", "-")
        base_name = f"{safe_inst}_{stem}"
    else:
        base_name = stem

    dest = arranjo_dir / f"{base_name}{ext}"
    if dest.exists():
        dest = arranjo_dir / f"{base_name}_{uuid.uuid4().hex[:8]}{ext}"

    dest.write_bytes(file_bytes)
    caminho = str(dest.relative_to(UPLOADS_ROOT))
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    logger.info("[Acervo] Salvo: %s (%d bytes)", caminho, len(file_bytes))
    return caminho, len(file_bytes), file_hash


def salvar_upload(
    upload: UploadFile,
    arranjo_id: int,
    tipo: str,
    instrumento_nome: str | None = None,
) -> tuple[str, int, str]:
    """Atalho: valida UploadFile e salva no disco."""
    file_bytes, _, size = validar_arquivo_partitura(upload)
    caminho, _, file_hash = salvar_documento(
        file_bytes, upload.filename, arranjo_id, tipo, instrumento_nome
    )
    return caminho, size, file_hash


def url_download(caminho: str) -> str:
    """URL pública para arquivo em /uploads."""
    return f"/uploads/{caminho}"
