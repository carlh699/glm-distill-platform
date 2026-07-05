"""模型评估 Celery 任务"""
import os
import time
import json
from datetime import datetime
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.celery_app import app
from app.config import settings
from app.models import TaskStatus

SYNC_DB_URL = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
sync_engine = create_engine(SYNC_DB_URL, pool_size=5)
SyncSession = sessionmaker(bind=sync_engine)


def _get_task(task_id: str):
    with SyncSession() as db:
        result = db.execute(text("SELECT * FROM distill_tasks WHERE id = :id"), {"id": task_id})
        return dict(result.mappings().first())


def _insert_evaluation(data: dict):
    with SyncSession() as db:
        cols = ", ".join(data.keys())
        vals = ", ".join(f":{k}" for k in data.keys())
        db.execute(text(f"INSERT INTO evaluations ({cols}) VALUES ({vals})"), data)
        db.commit()


@app.task(name="app.tasks.eval_tasks.run_evaluation")
def run_evaluation(task_id: str):
    """对蒸馏后的模型进行评估"""
    logger.info(f"[Celery] Starting evaluation for task: {task_id}")

    task = _get_task(task_id)
    if not task:
        return {"error": "task not found"}

    model_path = task.get("output_model_path")
    if not model_path:
        return {"error": "no output model"}

    try:
        # Download model from MinIO
        from app.services.storage import MinIOClient
        minio_client = MinIOClient()

        local_model_dir = f"/tmp/eval_model_{task_id}"
        os.makedirs(local_model_dir, exist_ok=True)

        bucket, prefix = model_path.split("/", 1)
        for obj in minio_client.list_objects(bucket, prefix=prefix):
            rel_path = obj.object_name[len(prefix):].lstrip("/")
            local_file = os.path.join(local_model_dir, rel_path)
            os.makedirs(os.path.dirname(local_file), exist_ok=True)
            minio_client.download_file(bucket, obj.object_name, local_file)

        # Run evaluation
        from app.engine.evaluation import evaluate_model
        metrics = evaluate_model(model_path=local_model_dir)

        # Save to DB
        import uuid
        _insert_evaluation({
            "id": str(uuid.uuid4()),
            "task_id": task_id,
            "model_path": model_path,
            "perplexity": metrics.get("perplexity"),
            "bleu": metrics.get("bleu"),
            "rouge_l": metrics.get("rouge_l"),
            "accuracy": metrics.get("accuracy"),
            "inference_latency_ms": metrics.get("inference_latency_ms"),
            "model_size_mb": metrics.get("model_size_mb"),
            "custom_metrics": json.dumps(metrics.get("custom", {})),
            "created_at": datetime.utcnow(),
        })

        logger.info(f"[Celery] Evaluation for {task_id}: {metrics}")
        return {"task_id": task_id, "metrics": metrics}

    except Exception as e:
        logger.exception(f"Evaluation failed: {e}")
        raise
