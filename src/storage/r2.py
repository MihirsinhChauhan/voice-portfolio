"""
R2 (S3-compatible) storage client for session reports and audio.
Configure via R2_ENDPOINT, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY.
"""
from __future__ import annotations

from src.config.settings import settings


def _require_r2_config() -> None:
    if not all(
        [
            settings.R2_ENDPOINT,
            settings.R2_BUCKET,
            settings.R2_ACCESS_KEY_ID,
            settings.R2_SECRET_ACCESS_KEY,
        ]
    ):
        raise RuntimeError(
            "R2 is not configured. Set R2_ENDPOINT, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY."
        )


def _client():
    """Lazy S3 client configured for R2."""
    _require_r2_config()
    import boto3

    return boto3.client(
        service_name="s3",
        endpoint_url=settings.R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """
    Upload bytes to R2 at the given key. Returns the key.
    Key format example: reports/{room_name}/{session_id}.json
    """
    c = _client()
    bucket = settings.R2_BUCKET
    c.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


def download_bytes(key: str) -> bytes:
    """Download object from R2 as bytes. Raises if key does not exist."""
    c = _client()
    bucket = settings.R2_BUCKET
    resp = c.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def delete(key: str) -> None:
    """Delete object at key. No-op if key does not exist."""
    c = _client()
    bucket = settings.R2_BUCKET
    c.delete_object(Bucket=bucket, Key=key)


def exists(key: str) -> bool:
    """Return True if an object exists at key."""
    c = _client()
    bucket = settings.R2_BUCKET
    try:
        c.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False
