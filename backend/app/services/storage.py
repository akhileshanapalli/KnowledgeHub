import io
import os
import logging
from typing import Optional, BinaryIO
import boto3
from botocore.exceptions import ClientError
from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self):
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self.access_key = settings.S3_ACCESS_KEY
        self.secret_key = settings.S3_SECRET_KEY
        self.bucket_name = settings.S3_BUCKET_NAME
        self.region = settings.S3_REGION
        self.use_ssl = settings.S3_USE_SSL

        self._s3_client = None
        self._local_fallback_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "local_storage")

    @property
    def client(self):
        if settings.ENVIRONMENT == "test":
            return None
        if self._s3_client is None:
            try:
                from botocore.client import Config
                boto_config = Config(connect_timeout=1, read_timeout=1, retries={"max_attempts": 1})
                self._s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region,
                    use_ssl=self.use_ssl,
                    config=boto_config,
                )
            except Exception as e:
                logger.warning(f"Could not initialize S3 client: {e}. Falling back to local disk storage.")
                self._s3_client = None
        return self._s3_client

    def ensure_bucket_exists(self) -> None:
        client = self.client
        if client:
            try:
                client.head_bucket(Bucket=self.bucket_name)
            except ClientError:
                try:
                    client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Created S3 bucket: {self.bucket_name}")
                except Exception as e:
                    logger.warning(f"Could not create bucket {self.bucket_name}: {e}")
        else:
            os.makedirs(self._local_fallback_dir, exist_ok=True)

    def upload_file(self, file_obj: BinaryIO, storage_path: str, content_type: Optional[str] = None) -> str:
        client = self.client
        if client:
            try:
                self.ensure_bucket_exists()
                extra_args = {}
                if content_type:
                    extra_args["ContentType"] = content_type

                file_obj.seek(0)
                client.upload_fileobj(
                    file_obj,
                    self.bucket_name,
                    storage_path,
                    ExtraArgs=extra_args if extra_args else None,
                )
                return storage_path
            except Exception as e:
                logger.warning(f"S3 upload failed ({e}). Storing file locally.")

        # Local disk fallback
        local_target = os.path.join(self._local_fallback_dir, storage_path)
        os.makedirs(os.path.dirname(local_target), exist_ok=True)
        file_obj.seek(0)
        with open(local_target, "wb") as f:
            f.write(file_obj.read())
        return storage_path

    def download_file(self, storage_path: str) -> bytes:
        client = self.client
        if client:
            try:
                buf = io.BytesIO()
                client.download_fileobj(self.bucket_name, storage_path, buf)
                buf.seek(0)
                return buf.read()
            except Exception as e:
                logger.warning(f"S3 download failed ({e}). Checking local fallback.")

        local_target = os.path.join(self._local_fallback_dir, storage_path)
        if os.path.exists(local_target):
            with open(local_target, "rb") as f:
                return f.read()
        raise FileNotFoundError(f"Storage object not found at {storage_path}")

    def delete_file(self, storage_path: str) -> None:
        client = self.client
        if client:
            try:
                client.delete_object(Bucket=self.bucket_name, Key=storage_path)
            except Exception as e:
                logger.warning(f"S3 delete failed: {e}")

        local_target = os.path.join(self._local_fallback_dir, storage_path)
        if os.path.exists(local_target):
            try:
                os.remove(local_target)
            except Exception as e:
                logger.warning(f"Local file removal failed: {e}")


storage_service = StorageService()
