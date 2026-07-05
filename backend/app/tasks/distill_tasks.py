"""蒸馏训练 Celery 任务"""
import os
import tempfile
import json
from datetime import datetime
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.celery_app import app
from app.config import settings
from app.models import TaskStatus, DistillStrategy

# ─── 同步数据库连接 (Celery worker 不支持 async, 懒加载避免 import 时连接) ───
SYNC_DB_URL = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
_sync_engine = None
SyncSession = None

def _get_sync_engine():
    global _sync_engine, SyncSession
    if _sync_engine is None:
        _sync_engine = create_engine(SYNC_DB_URL, pool_size=5, max_overflow=10)
        SyncSession = sessionmaker(bind=_sync_engine)
    return _sync_engine

def _get_sync_session():
    _get_sync_engine()
    return SyncSession()


def _get_task(task_id: str):
    """从 DB 读取任务配置"""
    with _get_sync_session() as db:
        result = db.execute(text("SELECT * FROM distill_tasks WHERE id = :id"), {"id": task_id})
        row = result.mappings().first()
        return dict(row) if row else None


def _update_task(task_id: str, **fields):
    """更新任务状态"""
    with _get_sync_session() as db:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        db.execute(text(f"UPDATE distill_tasks SET {sets} WHERE id = :id"), {"id": task_id, **fields})
        db.commit()


@app.task(name="app.tasks.distill_tasks.run_distillation", bind=True, max_retries=2)
def run_distillation(self, task_id: str, node_id: str = ""):
    """主蒸馏训练任务

    Args:
        task_id: 蒸馏任务 ID
        node_id: 算力节点 ID (用于训练完成后释放)
    """
    logger.info(f"[Celery] Starting distillation task: {task_id} on node: {node_id}")

    task = _get_task(task_id)
    if not task:
        logger.error(f"Task {task_id} not found in DB")
        return {"error": "task not found"}

    _update_task(
        task_id,
        status=TaskStatus.RUNNING.value,
        started_at=datetime.utcnow(),
        celery_task_id=self.request.id,
    )

    try:
        # ─── 解析模型路径 ───
        teacher_id = task["teacher_model_id"]
        student_id = task["student_model_id"]

        with _get_sync_session() as db:
            teacher = db.execute(text("SELECT * FROM models WHERE id = :id"), {"id": teacher_id}).mappings().first()
            student = db.execute(text("SELECT * FROM models WHERE id = :id"), {"id": student_id}).mappings().first()
            dataset_row = db.execute(text("SELECT * FROM datasets WHERE id = :id"), {"id": task["dataset_id"]}).mappings().first()

        teacher_path = dict(teacher).get("huggingface_id") or dict(teacher).get("local_path") or settings.TEACHER_MODEL_PATH
        student_path = dict(student).get("huggingface_id") or dict(student).get("local_path") or settings.STUDENT_MODEL_PATH
        dataset_minio_path = dict(dataset_row)["file_path"]

        # ─── 下载数据集到本地 ───
        from app.services.storage import MinIOClient
        minio_client = MinIOClient()
        bucket, obj_name = dataset_minio_path.split("/", 1)
        local_data_path = f"/tmp/dataset_{task_id}.jsonl"
        minio_client.download_file(bucket, obj_name, local_data_path)
        logger.info(f"Downloaded dataset to {local_data_path}")

        # ─── 如果是 Response-based KD, 先生成 Teacher response ───
        strategy = task["strategy"]
        train_data_path = local_data_path

        if strategy == DistillStrategy.RESPONSE_KD.value:
            logger.info("Response-based KD: generating teacher responses first")
            from app.engine.teacher_generation import generate_teacher_data

            # 判断 Teacher 是 API 还是本地
            teacher_base = dict(teacher).get("base_model", "")
            if teacher_base.startswith("glm-") and "huggingface" not in str(dict(teacher).get("huggingface_id", "")):
                # API 调用
                teacher_data_path = f"/tmp/teacher_data_{task_id}.jsonl"
                generate_teacher_data(
                    dataset_path=local_data_path,
                    output_path=teacher_data_path,
                    teacher_source="api",
                    api_key=settings.ZHIPU_API_KEY,
                    api_model=teacher_base,
                )
                train_data_path = teacher_data_path
            else:
                # 本地模型生成
                teacher_data_path = f"/tmp/teacher_data_{task_id}.jsonl"
                generate_teacher_data(
                    dataset_path=local_data_path,
                    output_path=teacher_data_path,
                    teacher_source="local",
                    local_model_path=teacher_path,
                )
                train_data_path = teacher_data_path

        # ─── 设置输出目录 ───
        output_dir = f"/data/models/distill_{task_id}"

        # ─── 运行蒸馏训练 ───
        from app.engine.distillation import run_distillation_training

        metrics = run_distillation_training(
            task_id=task_id,
            teacher_model_path=teacher_path,
            student_model_path=student_path,
            dataset_path=train_data_path,
            strategy=strategy,
            temperature=task["distill_temperature"],
            alpha=task["distill_alpha"],
            learning_rate=task["learning_rate"],
            batch_size=task["batch_size"],
            num_epochs=task["num_epochs"],
            max_seq_length=task["max_seq_length"],
            warmup_steps=task["warmup_steps"],
            save_steps=task["save_steps"],
            eval_steps=task["eval_steps"],
            gradient_accumulation_steps=task["gradient_accumulation_steps"],
            use_lora=task["use_lora"],
            lora_rank=task["lora_rank"],
            lora_alpha=task["lora_alpha"],
            output_dir=output_dir,
            deepspeed_config=task.get("deepspeed_config"),
            mlflow_tracking_uri=settings.MLFLOW_TRACKING_URI,
            mlflow_run_name=f"distill-{task_id}",
        )

        # ─── 上传模型到 MinIO ───
        final_dir = os.path.join(output_dir, "final")
        model_object_prefix = f"models/distill_{task_id}"

        for f in os.listdir(final_dir):
            if f.endswith((".bin", ".safetensors", ".json", ".txt", ".model")):
                minio_client.upload_file(
                    settings.MINIO_BUCKET_MODELS,
                    f"{model_object_prefix}/{f}",
                    os.path.join(final_dir, f),
                )

        minio_model_path = f"{settings.MINIO_BUCKET_MODELS}/{model_object_prefix}"

        # ─── 更新任务状态 ───
        _update_task(
            task_id,
            status=TaskStatus.SUCCESS.value,
            progress=1.0,
            current_step=metrics["total_steps"],
            total_steps=metrics["total_steps"],
            output_model_path=minio_model_path,
            metrics=metrics,
            finished_at=datetime.utcnow(),
        )

        # ─── 释放算力节点 ───
        if node_id:
            _release_node(node_id)

        logger.info(f"[Celery] Distillation task {task_id} completed: {metrics}")
        return {"task_id": task_id, "status": "success", "metrics": metrics}

    except Exception as e:
        logger.exception(f"[Celery] Distillation task {task_id} failed: {e}")
        _update_task(
            task_id,
            status=TaskStatus.FAILED.value,
            error_message=str(e),
            finished_at=datetime.utcnow(),
        )
        # 失败也释放节点
        if node_id:
            _release_node(node_id)
        raise


def _release_node(node_id: str):
    """训练完成后释放算力节点"""
    try:
        with _get_sync_session() as db:
            db.execute(text(
                "UPDATE compute_nodes SET status = 'online', current_task_id = NULL WHERE id = :id"
            ), {"id": node_id})
            db.commit()
            logger.info(f"Released compute node {node_id}")
    except Exception as e:
        logger.error(f"Failed to release node {node_id}: {e}")


@app.task(name="app.tasks.distill_tasks.update_progress")
def update_progress(task_id: str, progress: float, current_step: int, total_steps: int):
    """供训练过程中回调更新进度"""
    _update_task(task_id, progress=progress, current_step=current_step, total_steps=total_steps)
