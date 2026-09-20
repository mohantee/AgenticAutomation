"""Environment-aware file reader — local filesystem or S3."""

from __future__ import annotations

import logging
import os

from agenticautomation.config import config

logger = logging.getLogger(__name__)


def read_file(file_key: str) -> str:
    """Read a document's text content from the appropriate source.

    In dev mode, reads from the local input path.
    In test/prod, reads from the S3 input bucket.

    Args:
        file_key: Either a local file path (dev) or an S3 object key (test/prod).

    Returns:
        The document content as a UTF-8 string.

    Raises:
        FileNotFoundError: If the file does not exist.
        RuntimeError: If the file cannot be read.
    """
    if config.storage_backend == "local":
        return _read_local(file_key)
    else:
        return _read_s3(file_key)


def _read_local(file_key: str) -> str:
    """Read a file from the local filesystem.

    Tries the file_key as-is first, then falls back to joining with
    the configured local_input_path.
    """
    # Try direct path first
    if os.path.isfile(file_key):
        path = file_key
    else:
        # Try relative to input directory
        path = os.path.join(config.local_input_path, os.path.basename(file_key))

    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {file_key} (tried {path})")

    logger.info("Reading local file: %s", path)
    with open(path, encoding="utf-8") as f:
        return f.read()


def _read_s3(file_key: str) -> str:
    """Read a file from the S3 input bucket."""
    import boto3

    client = boto3.client("s3", region_name=config.aws_region)
    bucket = config.s3_input_bucket

    logger.info("Reading S3 object: s3://%s/%s", bucket, file_key)
    try:
        response = client.get_object(Bucket=bucket, Key=file_key)
        body = response["Body"].read()
        return body.decode("utf-8")
    except client.exceptions.NoSuchKey:
        raise FileNotFoundError(f"S3 object not found: s3://{bucket}/{file_key}")
    except Exception as e:
        raise RuntimeError(f"Failed to read s3://{bucket}/{file_key}: {e}") from e
