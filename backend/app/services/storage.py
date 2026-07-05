"""MinIO 对象存储客户端"""
import io
from minio import Minio
from loguru import logger
from app.config import settings


class MinIOClient:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self._ensure_buckets()

    def _ensure_buckets(self):
        for bucket in [
            settings.MINIO_BUCKET_MODELS,
            settings.MINIO_BUCKET_DATASETS,
            settings.MINIO_BUCKET_ARTIFACTS,
        ]:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
                logger.info(f"Created MinIO bucket: {bucket}")

    def upload_bytes(self, bucket: str, object_name: str, data: bytes, content_type: str = "application/octet-stream"):
        self.client.put_object(bucket, object_name, io.BytesIO(data), len(data), content_type=content_type)
        logger.info(f"Uploaded {bucket}/{object_name} ({len(data)} bytes)")

    def download_bytes(self, bucket: str, object_name: str) -> bytes:
        resp = self.client.get_object(bucket, object_name)
        data = resp.read()
        resp.close()
        resp.release_conn()
        return data

    def upload_file(self, bucket: str, object_name: str, file_path: str):
        import os
        self.client.fput_object(bucket, object_name, file_path)
        logger.info(f"Uploaded file {file_path} -> {bucket}/{object_name}")

    def download_file(self, bucket: str, object_name: str, file_path: str):
        self.client.fget_object(bucket, object_name, file_path)
        logger.info(f"Downloaded {bucket}/{object_name} -> {file_path}")

    def list_objects(self, bucket: str, prefix: str = ""):
        return list(self.client.list_objects(bucket, prefix=prefix, recursive=True))

    def get_presigned_url(self, bucket: str, object_name: str, expires_hours: int = 1) -> str:
        from datetime import timedelta
        return self.client.presigned_get_object(bucket, object_name, expires=timedelta(hours=expires_hours))
