"""Deployments API - 模型部署管理"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Deployment
from app.schemas import DeploymentCreate, DeploymentResponse, ApiResponse
from app.tasks.deploy_tasks import run_deployment

router = APIRouter(prefix="/deployments", tags=["部署管理"])


@router.get("", response_model=list[DeploymentResponse])
async def list_deployments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Deployment).order_by(Deployment.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    return result.scalars().all()


@router.post("", response_model=DeploymentResponse, status_code=201)
async def create_deployment(data: DeploymentCreate, db: AsyncSession = Depends(get_db)):
    dep = Deployment(**data.model_dump())
    db.add(dep)
    await db.flush()
    result = run_deployment.delay(dep.id)
    return dep


@router.get("/{dep_id}", response_model=DeploymentResponse)
async def get_deployment(dep_id: str, db: AsyncSession = Depends(get_db)):
    dep = await db.get(Deployment, dep_id)
    if not dep:
        raise HTTPException(404, "部署不存在")
    return dep


@router.post("/{dep_id}/stop")
async def stop_deployment(dep_id: str, db: AsyncSession = Depends(get_db)):
    dep = await db.get(Deployment, dep_id)
    if not dep:
        raise HTTPException(404, "部署不存在")
    dep.status = "stopped"
    from datetime import datetime
    dep.stopped_at = datetime.utcnow()
    return ApiResponse(message="已停止")


@router.delete("/{dep_id}")
async def delete_deployment(dep_id: str, db: AsyncSession = Depends(get_db)):
    dep = await db.get(Deployment, dep_id)
    if not dep:
        raise HTTPException(404, "部署不存在")
    await db.delete(dep)
    return ApiResponse(message="已删除")
