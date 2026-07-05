"""Teacher 数据生成 Celery 任务"""
import os
from loguru import logger

from app.celery_app import app
from app.config import settings


@app.task(name="app.tasks.generation_tasks.generate_teacher_responses")
def generate_teacher_responses(
    dataset_path: str,
    output_path: str,
    teacher_source: str = "api",
    api_key: str = "",
    api_model: str = "glm-4-plus",
    local_model_path: str = "",
):
    """异步生成 Teacher soft labels"""
    from app.engine.teacher_generation import generate_teacher_data

    result_path = generate_teacher_data(
        dataset_path=dataset_path,
        output_path=output_path,
        teacher_source=teacher_source,
        api_key=api_key or settings.ZHIPU_API_KEY,
        api_model=api_model,
        local_model_path=local_model_path or settings.TEACHER_MODEL_PATH,
    )

    logger.info(f"Teacher data generated: {result_path}")
    return {"output_path": result_path}
