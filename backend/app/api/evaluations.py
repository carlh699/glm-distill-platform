"""Evaluations API - 模型评估"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Evaluation, DistillTask
from app.schemas import EvaluationResponse, ApiResponse
from app.tasks.eval_tasks import run_evaluation

router = APIRouter(prefix="/evaluations", tags=["评估管理"])


@router.get("", response_model=list[EvaluationResponse])
async def list_evaluations(
    task_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Evaluation)
    if task_id:
        query = query.where(Evaluation.task_id == task_id)
    query = query.order_by(Evaluation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{eval_id}", response_model=EvaluationResponse)
async def get_evaluation(eval_id: str, db: AsyncSession = Depends(get_db)):
    ev = await db.get(Evaluation, eval_id)
    if not ev:
        raise HTTPException(404, "评估记录不存在")
    return ev


@router.post("/task/{task_id}")
async def trigger_evaluation(task_id: str, db: AsyncSession = Depends(get_db)):
    """触发对蒸馏后模型的评估"""
    task = await db.get(DistillTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.status.value != "success":
        raise HTTPException(400, "任务未完成，无法评估")
    result = run_evaluation.delay(task_id)
    return {"message": "评估已提交", "celery_task_id": result.id}
