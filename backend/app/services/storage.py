"""MinIO 对象存储客户端 — MinIO 不可用时自动降级到本地文件"""
import io
import os
from loguru import logger
from app.config import settings

LOCAL_STORAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".local_storage")

_singleton = None


class MinIOClient:
    def __init__(self):
        self._minio = None
        self._available = False
        try:
            from minio import Minio
            self._minio = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
            self._ensure_buckets()
            self._available = True
        except Exception as e:
            logger.warning(f"MinIO not available, using local file storage")
            os.makedirs(LOCAL_STORAGE, exist_ok=True)

    def _ensure_buckets(self):
        for bucket in [settings.MINIO_BUCKET_MODELS, settings.MINIO_BUCKET_DATASETS, settings.MINIO_BUCKET_ARTIFACTS]:
            self._minio.bucket_exists(bucket)  # fail fast

    @property
    def available(self):
        return self._available

    def upload_bytes(self, bucket: str, object_name: str, data: bytes, content_type: str = "application/octet-stream"):
        if self._available:
            self._minio.put_object(bucket, object_name, io.BytesIO(data), len(data), content_type=content_type)
            logger.info(f"Uploaded {bucket}/{object_name} ({len(data)} bytes)")
        else:
            local_path = os.path.join(LOCAL_STORAGE, bucket, object_name.replace("/", os.sep))
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(data)
            logger.info(f"Stored locally {bucket}/{object_name} ({len(data)} bytes) → {local_path}")

    def download_bytes(self, bucket: str, object_name: str) -> bytes:
        if self._available:
            resp = self._minio.get_object(bucket, object_name)
            data = resp.read()
            resp.close()
            resp.release_conn()
            return data
        else:
            local_path = os.path.join(LOCAL_STORAGE, bucket, object_name.replace("/", os.sep))
            with open(local_path, "rb") as f:
                return f.read()

    def upload_file(self, bucket: str, object_name: str, file_path: str):
        if self._available:
            self._minio.fput_object(bucket, object_name, file_path)
        else:
            import shutil
            local_path = os.path.join(LOCAL_STORAGE, bucket, object_name.replace("/", os.sep))
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            shutil.copy2(file_path, local_path)
        logger.info(f"Uploaded {file_path} → {bucket}/{object_name}")

    def download_file(self, bucket: str, object_name: str, file_path: str):
        if self._available:
            self._minio.fget_object(bucket, object_name, file_path)
        else:
            import shutil
            local_path = os.path.join(LOCAL_STORAGE, bucket, object_name.replace("/", os.sep))
            shutil.copy2(local_path, file_path)
        logger.info(f"Downloaded {bucket}/{object_name} → {file_path}")

    def list_objects(self, bucket: str, prefix: str = ""):
        if self._available:
            return list(self._minio.list_objects(bucket, prefix=prefix, recursive=True))
        else:
            local_dir = os.path.join(LOCAL_STORAGE, bucket)
            if not os.path.isdir(local_dir):
                return []
            result = []
            for root, dirs, files in os.walk(local_dir):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, local_dir).replace(os.sep, "/")
                    if rel.startswith(prefix):
                        result.append(type("Obj", (), {"object_name": rel, "size": os.path.getsize(full)})())
            return result

    def get_presigned_url(self, bucket: str, object_name: str, expires_hours: int = 1) -> str:
        if self._available:
            from datetime import timedelta
            return self._minio.presigned_get_object(bucket, object_name, expires=timedelta(hours=expires_hours))
        else:
            return f"local://{bucket}/{object_name}"


def get_storage() -> MinIOClient:
    """Singleton — avoid reconnecting to MinIO on every request."""
    global _singleton
    if _singleton is None:
        _singleton = MinIOClient()
    return _singleton
