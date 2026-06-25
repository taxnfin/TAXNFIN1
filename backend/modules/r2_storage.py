"""Cloudflare R2 storage via boto3 (S3-compatible API)."""
import boto3
from botocore.exceptions import ClientError
from core.config import settings
import logging

logger = logging.getLogger(__name__)


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


BUCKET = settings.R2_BUCKET_NAME


def upload_file(file_bytes: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to R2 and return the object key (use presigned URL for access)."""
    client = _client()
    client.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    logger.info(f"[R2] Uploaded {key} ({len(file_bytes)} bytes)")
    return key


def download_file(key: str) -> bytes:
    """Download object from R2 and return bytes."""
    client = _client()
    response = client.get_object(Bucket=BUCKET, Key=key)
    return response["Body"].read()


def delete_file(key: str) -> bool:
    """Delete object from R2. Returns True on success."""
    try:
        client = _client()
        client.delete_object(Bucket=BUCKET, Key=key)
        logger.info(f"[R2] Deleted {key}")
        return True
    except ClientError as e:
        logger.error(f"[R2] Delete failed for {key}: {e}")
        return False


def generate_presigned_url(key: str, expires: int = 3600) -> str:
    """Generate a temporary presigned URL for downloading a private object."""
    client = _client()
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=expires,
    )
    return url
