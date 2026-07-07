"""Celery 应用配置"""
from celery import Celery
from app.config import settings
import logging

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
    # Fail fast when broker is down instead of hanging
    broker_connection_retry_on_startup=False,
    broker_connection_max_retries=1,
    broker_connection_timeout=3,
)

app.autodiscover_tasks([
    "app.tasks.distill_tasks",
    "app.tasks.eval_tasks",
    "app.tasks.deploy_tasks",
    "app.tasks.generation_tasks",
])


def celery_available() -> bool:
    """Check if Celery broker (Redis) is reachable without blocking."""
    try:
        conn = app.connection_for_write()
        conn.ensure_connection(max_retries=0, timeout=2)
        conn.close()
        return True
    except Exception:
        return False
