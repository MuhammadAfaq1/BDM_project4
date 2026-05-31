"""MinIO (S3) client."""

from __future__ import annotations

import boto3

from rico_pipeline.config import (
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_SECRET_KEY,
)


def get_s3():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )


def put_bytes(key: str, body: bytes, content_type: str | None = None) -> None:
    kwargs = {"Bucket": MINIO_BUCKET, "Key": key, "Body": body}
    if content_type:
        kwargs["ContentType"] = content_type
    get_s3().put_object(**kwargs)


def get_bytes(key: str) -> bytes:
    return get_s3().get_object(Bucket=MINIO_BUCKET, Key=key)["Body"].read()


def list_keys(prefix: str = "") -> list[str]:
    resp = get_s3().list_objects_v2(Bucket=MINIO_BUCKET, Prefix=prefix)
    return sorted(o["Key"] for o in resp.get("Contents", []))
