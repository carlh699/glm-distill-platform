"""全局配置 - 从环境变量读取"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ─── 应用 ───
    APP_NAME: str = "GLM Distill Platform"
    SECRET_KEY: str = "dev-secret-key-change-in-prod"
    API_PREFIX: str = "/api/v1"

    # ─── 数据库 ───
    DATABASE_URL: str = "postgresql+asyncpg://distill...@localhost:5432/distill_platform"

    # ─── Redis / Celery ───
    CELERY_BROKER_URL: str = "redis://:redis123@localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://:redis123@localhost:6379/1"

    # ─── MinIO ───
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET_MODELS: str = "models"
    MINIO_BUCKET_DATASETS: str = "datasets"
    MINIO_BUCKET_ARTIFACTS: str = "mlflow-artifacts"
    MINIO_SECURE: bool = False

    # ─── MLflow ───
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MLFLOW_EXPERIMENT: str = "glm-distill"

    # ─── 智谱 GLM API ───
    ZHIPU_API_KEY: str = ""

    # ─── HuggingFace ───
    HF_HOME: str = "/data/hf_cache"
    HF_TOKEN: str = ""

    # ─── 模型路径 ───
    TEACHER_MODEL_PATH: str = "THUDM/glm-4-9b-chat"
    STUDENT_MODEL_PATH: str = "THUDM/chatglm3-6b"

    # ─── 训练默认参数 ───
    DEFAULT_LEARNING_RATE: float = 5e-5
    DEFAULT_BATCH_SIZE: int = 4
    DEFAULT_EPOCHS: int = 3
    DEFAULT_MAX_SEQ_LEN: int = 2048

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
