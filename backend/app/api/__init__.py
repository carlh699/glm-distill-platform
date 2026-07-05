"""API 路由聚合"""
from fastapi import APIRouter
from app.api import models, datasets, tasks, evaluations, deployments, compute_nodes

api_router = APIRouter()
api_router.include_router(models.router)
api_router.include_router(datasets.router)
api_router.include_router(tasks.router)
api_router.include_router(evaluations.router)
api_router.include_router(deployments.router)
api_router.include_router(compute_nodes.router)
