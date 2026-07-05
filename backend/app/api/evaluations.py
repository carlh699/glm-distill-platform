"""Evaluations API - 模型评估"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Evaluation, DistillTask
from app.schemas import EvaluationCompareRequest, EvaluationResponse, ApiResponse
from app.tasks.eval_tasks import run_evaluation

router = APIRouter(prefix="/evaluations", tags=["评估管理"])

METRIC_DIRECTIONS = {
    "accuracy": "desc",
    "bleu": "desc",
    "rouge_l": "desc",
    "perplexity": "asc",
    "inference_latency_ms": "asc",
    "model_size_mb": "asc",
}


def _evaluation_metrics(ev: Evaluation) -> dict:
    return {metric: getattr(ev, metric) for metric in METRIC_DIRECTIONS}


def _evaluation_summary(ev: Evaluation) -> dict:
    return {
        "id": ev.id,
        "task_id": ev.task_id,
        "model_path": ev.model_path,
        "metrics": _evaluation_metrics(ev),
        "teacher_metrics": ev.teacher_metrics or {},
        "custom_metrics": ev.custom_metrics or {},
        "created_at": ev.created_at.isoformat(),
    }


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


@router.post("/compare", response_model=ApiResponse)
async def compare_evaluations(data: EvaluationCompareRequest, db: AsyncSession = Depends(get_db)):
    """对比多个评估记录的核心指标"""
    result = await db.execute(select(Evaluation).where(Evaluation.id.in_(data.evaluation_ids)))
    found = {ev.id: ev for ev in result.scalars().all()}
    missing = [eval_id for eval_id in data.evaluation_ids if eval_id not in found]
    if missing:
        raise HTTPException(404, f"评估记录不存在: {', '.join(missing)}")

    evaluations = [found[eval_id] for eval_id in data.evaluation_ids]
    best = {}
    for metric, direction in METRIC_DIRECTIONS.items():
        candidates = [ev for ev in evaluations if getattr(ev, metric) is not None]
        if not candidates:
            continue
        best_ev = min(candidates, key=lambda ev: getattr(ev, metric)) if direction == "asc" else max(
            candidates, key=lambda ev: getattr(ev, metric)
        )
        best[metric] = {
            "evaluation_id": best_ev.id,
            "value": getattr(best_ev, metric),
        }

    return ApiResponse(
        message="评估对比完成",
        data={
            "items": [_evaluation_summary(ev) for ev in evaluations],
            "best": best,
        },
    )


@router.get("/leaderboard", response_model=ApiResponse)
async def get_evaluation_leaderboard(
    metric: str = Query("accuracy"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """按指定指标获取评估排行榜"""
    if metric not in METRIC_DIRECTIONS:
        raise HTTPException(400, f"不支持的排行榜指标: {metric}")

    column = getattr(Evaluation, metric)
    order_by = column.asc() if METRIC_DIRECTIONS[metric] == "asc" else column.desc()
    result = await db.execute(select(Evaluation).where(column.is_not(None)).order_by(order_by).limit(limit))
    evaluations = result.scalars().all()

    return ApiResponse(
        message="评估排行榜获取成功",
        data=[
            {
                "rank": index + 1,
                "evaluation_id": ev.id,
                "task_id": ev.task_id,
                "model_path": ev.model_path,
                "metric": metric,
                "metric_value": getattr(ev, metric),
                "metrics": _evaluation_metrics(ev),
                "teacher_metrics": ev.teacher_metrics or {},
                "custom_metrics": ev.custom_metrics or {},
            }
            for index, ev in enumerate(evaluations)
        ],
    )


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
