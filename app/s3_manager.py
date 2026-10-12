"""
Portal — Gerenciador de uploads para S3 (AWS ou Mock Local).
Suporta tanto desenvolvimento local (moto) quanto produção (AWS).
"""

import os
import logging
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from botocore.client import Config

logger = logging.getLogger("uvicorn.error")

# ──────────────────────────────────────────────────────────────────
# Configuração
# ──────────────────────────────────────────────────────────────────

# Modo: 'local' (mock moto) ou 'aws' (AWS real)
S3_MODE = os.getenv("S3_MODE", "local")

BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME", "portal-partituras-local")
REGION = os.getenv("AWS_S3_REGION", "sa-east-1")
URL_EXPIRY = int(os.getenv("AWS_S3_URL_EXPIRY_SECONDS", "604800"))  # 7 dias
PRESIGNED_URL_EXPIRY = int(os.getenv("AWS_S3_PRESIGNED_URL_EXPIRY", "900"))  # 15 min

# ──────────────────────────────────────────────────────────────────
# Inicializar S3 Client
# ──────────────────────────────────────────────────────────────────

if S3_MODE == "local":
    # Mock local com moto
    from moto import mock_s3

    # Ativa o mock
    mock_s3().start()

    # Cliente com configuração local
    s3_client = boto3.client(
        "s3",
        region_name=REGION,
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        endpoint_url="http://localhost:5000",  # Moto server (opcional)
    )

    # Criar bucket se não existir (apenas em mode local)
    try:
        s3_client.create_bucket(
            Bucket=BUCKET_NAME,
            CreateBucketConfiguration={"LocationConstraint": REGION} if REGION != "us-east-1" else {},
        )
        logger.info(f"[S3 LOCAL] Bucket '{BUCKET_NAME}' criado/verificado")
    except Exception as e:
        logger.debug(f"[S3 LOCAL] Bucket já existe: {e}")

else:
    # AWS real
    s3_client = boto3.client(
        "s3",
        region_name=REGION,
        config=Config(
            max_pool_connections=50,
            retries={"max_attempts": 3, "mode": "adaptive"},
            signature_version="s3v4",
        ),
    )
    logger.info(f"[S3 AWS] Conectado ao bucket '{BUCKET_NAME}' em {REGION}")


# ──────────────────────────────────────────────────────────────────
# Funções Públicas
# ──────────────────────────────────────────────────────────────────


def _arquivo_para_s3_key(arranjo_id: int, tipo_documento: str, versao: str, filename: str) -> str:
    """
    Gera chave S3 padrão para um arquivo.

    Formato: obras/arranjo_<id>/<tipo>/<versao>/<filename>
    Exemplo: obras/arranjo_123/grade/v1.0/abertura.pdf
    """
    ext = Path(filename).suffix.lower()
    safe_filename = Path(filename).stem.replace(" ", "_")
    return f"obras/arranjo_{arranjo_id}/{tipo_documento}/{versao}/{safe_filename}{ext}"


def upload_arquivo_partitura(
    arranjo_id: int,
    tipo_documento: str,
    versao: str,
    file_bytes: bytes,
    filename: str,
    metadata: dict = None,
) -> dict:
    """
    Upload de arquivo para S3.

    Args:
        arranjo_id: ID do arranjo
        tipo_documento: Tipo ('grade', 'parte_instrumento', etc)
        versao: Versão ('v1.0', 'v1.1', etc)
        file_bytes: Conteúdo do arquivo
        filename: Nome original do arquivo
        metadata: Dicionário com metadados adicionais

    Returns:
        {
            "s3_key": "obras/arranjo_123/grade/v1.0/file.pdf",
            "tamanho": 512000,
            "hash": "abc123...",
            "timestamp": "2026-06-12T10:30:00Z"
        }

    Raises:
        ClientError: Se falhar o upload
        ValueError: Se arquivo inválido
    """
    s3_key = _arquivo_para_s3_key(arranjo_id, tipo_documento, versao, filename)
    hash_arquivo = hashlib.sha256(file_bytes).hexdigest()

    try:
        meta = metadata or {}
        meta.update({
            "arranjo_id": str(arranjo_id),
            "tipo": tipo_documento,
            "versao": versao,
            "hash": hash_arquivo,
        })

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=file_bytes,
            ContentType="application/pdf",
            Metadata={k: str(v)[:255] for k, v in meta.items()},  # S3 limita metadados a 2KB
            ServerSideEncryption="AES256",
            StorageClass="STANDARD" if S3_MODE == "local" else "STANDARD_IA",
        )

        logger.info(
            f"[S3] Upload: {s3_key} ({len(file_bytes)} bytes) | "
            f"Hash: {hash_arquivo} | Mode: {S3_MODE}"
        )

        return {
            "s3_key": s3_key,
            "tamanho": len(file_bytes),
            "hash": hash_arquivo,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except ClientError as e:
        logger.error(f"[S3] Erro no upload: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[S3] Erro inesperado: {str(e)}", exc_info=True)
        raise


def gerar_url_temporaria(
    s3_key: str,
    expiry_seconds: int = None,
    force_download: bool = True,
) -> str:
    """
    Gera URL pré-assinada (presigned URL) para acesso temporário.

    Args:
        s3_key: Chave S3 do arquivo
        expiry_seconds: Expiração em segundos (default 15 min)
        force_download: Se True, força download (Content-Disposition: attachment)

    Returns:
        URL presigned válida por `expiry_seconds`
    """
    expiry = expiry_seconds or PRESIGNED_URL_EXPIRY

    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": s3_key,
                "ResponseContentDisposition": "attachment" if force_download else "inline",
            },
            ExpiresIn=expiry,
        )
        logger.debug(f"[S3] Presigned URL gerada: {s3_key} (expiry: {expiry}s)")
        return url

    except ClientError as e:
        logger.error(f"[S3] Erro ao gerar URL: {str(e)}")
        raise


def deletar_arquivo(s3_key: str) -> bool:
    """
    Deleta arquivo do S3 (soft delete com versionamento em produção).

    Args:
        s3_key: Chave S3 do arquivo

    Returns:
        True se sucesso, False se erro
    """
    try:
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
        logger.info(f"[S3] Deletado: {s3_key}")
        return True

    except ClientError as e:
        logger.error(f"[S3] Erro ao deletar: {str(e)}")
        return False


def verificar_arquivo_existente(s3_key: str) -> bool:
    """
    Verifica se arquivo existe no S3.

    Args:
        s3_key: Chave S3 do arquivo

    Returns:
        True se existe, False caso contrário
    """
    try:
        s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        logger.error(f"[S3] Erro ao verificar: {str(e)}")
        return False


def listar_versoes_documento(arranjo_id: int, tipo_documento: str) -> list[dict]:
    """
    Lista todas as versões de um documento no S3.

    Args:
        arranjo_id: ID do arranjo
        tipo_documento: Tipo do documento

    Returns:
        Lista de dicts com: key, size, modified
    """
    prefix = f"obras/arranjo_{arranjo_id}/{tipo_documento}/"

    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)

        if "Contents" not in response:
            return []

        return [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "modified": obj["LastModified"].isoformat(),
            }
            for obj in response["Contents"]
        ]

    except ClientError as e:
        logger.error(f"[S3] Erro ao listar: {str(e)}")
        return []


def health_check() -> dict:
    """
    Verifica se S3 está acessível.

    Returns:
        {"status": "ok", "mode": "local|aws", "bucket": "..."}
    """
    try:
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        return {
            "status": "ok",
            "mode": S3_MODE,
            "bucket": BUCKET_NAME,
            "region": REGION,
        }

    except ClientError as e:
        logger.error(f"[S3] Health check falhou: {str(e)}")
        return {
            "status": "error",
            "mode": S3_MODE,
            "bucket": BUCKET_NAME,
            "error": str(e),
        }


# ──────────────────────────────────────────────────────────────────
# Aliases para compatibilidade
# ──────────────────────────────────────────────────────────────────

# Para fácil uso em contextos de desenvolvimento/produção
upload_partitura = upload_arquivo_partitura
gerar_download_url = gerar_url_temporaria
