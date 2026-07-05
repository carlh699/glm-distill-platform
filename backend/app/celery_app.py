"""Celery 应用配置"""
from celery import Celery
from app.config import settings

app = Celery(
    "glm_distill",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.distill_tasks.*": {"queue": "training"},
        "app.tasks.eval_tasks.*": {"queue": "evaluation"},
        "app.tasks.deploy_tasks.*": {"queue": "generation"},
        "app.tasks.generation_tasks.*": {"queue": "generation"},
    },
    worker_max_retries=3,
)

app.autodiscover_tasks([
    "app.tasks.distill_tasks",
    "app.tasks.eval_tasks",
    "app.tasks.deploy_tasks",
    "app.tasks.generation_tasks",
])
