"""Distill Tasks API - 蒸馏任务管理"""
from loguru import logger
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import DistillTask, TaskStatus
from app.schemas import DistillTaskCreate, DistillTaskResponse, DistillTaskUpdate, ApiResponse
from app.tasks.distill_tasks import run_distillation

router = APIRouter(prefix="/tasks", tags=["蒸馏任务"])


@router.get("", response_model=list[DistillTaskResponse])
async def list_tasks(
    status: TaskStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(DistillTask)
    if status:
        query = query.where(DistillTask.status == status)
    query = query.order_by(DistillTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=DistillTaskResponse, status_code=201)
async def create_task(data: DistillTaskCreate, db: AsyncSession = Depends(get_db)):
    """创建蒸馏任务并提交到 Celery

    自动查找一个 online 的算力节点分配执行。
    如果没有在线节点，任务保持 PENDING 等待。
    """
    from app.models import ComputeNode
    from sqlalchemy import select as sa_select

    task = DistillTask(**data.model_dump())
    db.add(task)
    await db.flush()

    # 查找可用算力节点 (优先选 GPU 数最多且空闲的)
    node_result = await db.execute(
        sa_select(ComputeNode)
        .where(ComputeNode.status == "online")
        .order_by(ComputeNode.gpu_count.desc(), ComputeNode.gpu_total_vram_gb.desc())
        .limit(1)
    )
    node = node_result.scalars().first()

    if node:
        # 有可用节点，提交训练任务
        from app.celery_app import celery_available
        if celery_available():
            try:
                celery_result = run_distillation.delay(task.id, node.id)
                task.celery_task_id = celery_result.id
                task.status = TaskStatus.PENDING
                node.status = "busy"
                node.current_task_id = task.id
                logger.info(f"Task {task.id} assigned to node {node.name} ({node.gpu_count} GPU)")
            except Exception as e:
                logger.warning(f"Celery dispatch failed: {e}")
                task.status = TaskStatus.PENDING
        else:
            logger.warning(f"Celery broker unavailable, task {task.id} queued but not started")
            task.status = TaskStatus.PENDING
    else:
        # 没有可用节点，等待
        task.status = TaskStatus.PENDING
        task.error_message = "等待算力节点连接..."
        logger.warning(f"No available compute node for task {task.id}, waiting...")

    await db.flush()
    return task


@router.get("/{task_id}", response_model=DistillTaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(DistillTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@router.put("/{task_id}", response_model=DistillTaskResponse)
async def update_task(task_id: str, data: DistillTaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await db.get(DistillTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    return task


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(DistillTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.celery_task_id:
        from app.celery_app import app as celery_app
        celery_app.control.revoke(task.celery_task_id, terminate=True)
    task.status = TaskStatus.CANCELLED
    return ApiResponse(message="已取消")


@router.delete("/{task_id}")
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(DistillTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    await db.delete(task)
    return ApiResponse(message="已删除")


# ─── WebSocket 实时进度推送 ───
@router.websocket("/{task_id}/ws")
async def task_progress_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        import asyncio, json
        from app.database import async_session
        while True:
            async with async_session() as db:
                task = await db.get(DistillTask, task_id)
                if not task:
                    await websocket.send_json({"error": "任务不存在"})
                    break
                await websocket.send_json({
                    "status": task.status.value,
                    "progress": task.progress,
                    "current_step": task.current_step,
                    "total_steps": task.total_steps,
                    "metrics": task.metrics,
                })
                if task.status in (TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED):
                    break
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass
