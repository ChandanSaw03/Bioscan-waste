"""S3 integration helper for uploading files and logs via IAM roles."""

import os
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None


def get_s3_bucket() -> str | None:
    """Return the bucket name if configured, otherwise None."""
    return os.environ.get("BIOSCAN_S3_BUCKET")


def upload_to_s3(local_path: str | Path, s3_key: str) -> bool:
    """Upload a local file to S3 using IAM role credentials.
    
    Returns:
        True if upload succeeded or if S3 was not configured (skipped silently).
        False if an error occurred during upload.
    """
    bucket = get_s3_bucket()
    if not bucket or not boto3:
        return True  # Silently skip if not configured or boto3 is missing

    s3_client = boto3.client("s3")
    try:
        s3_client.upload_file(str(local_path), bucket, s3_key)
        return True
    except (BotoCoreError, ClientError) as e:
        print(f"Failed to upload {local_path} to S3 bucket {bucket}: {e}")
        return False
