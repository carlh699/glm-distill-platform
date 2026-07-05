"""Compute Nodes API — 算力节点连接管理"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import ComputeNode
from app.schemas import (
    ComputeNodeCreate, ComputeNodeResponse, ComputeNodeConnect,
    GpuStatsResponse, ApiResponse,
)
from app.engine.compute_detector import full_detect, get_gpu_stats, get_cpu_stats, detect_ram, get_disk_free
from loguru import logger

router = APIRouter(prefix="/compute-nodes", tags=["算力节点"])


@router.get("", response_model=list[ComputeNodeResponse])
async def list_nodes(
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(ComputeNode)
    if status:
        query = query.where(ComputeNode.status == status)
    query = query.order_by(ComputeNode.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=ComputeNodeResponse, status_code=201)
async def create_node(data: ComputeNodeCreate, db: AsyncSession = Depends(get_db)):
    """注册算力节点（注册后需调用 /connect 检测硬件并连接）"""
    node = ComputeNode(**data.model_dump())
    db.add(node)
    await db.flush()
    return node


@router.get("/{node_id}", response_model=ComputeNodeResponse)
async def get_node(node_id: str, db: AsyncSession = Depends(get_db)):
    node = await db.get(ComputeNode, node_id)
    if not node:
        raise HTTPException(404, "算力节点不存在")
    return node


@router.delete("/{node_id}")
async def delete_node(node_id: str, db: AsyncSession = Depends(get_db)):
    node = await db.get(ComputeNode, node_id)
    if not node:
        raise HTTPException(404, "算力节点不存在")
    await db.delete(node)
    return ApiResponse(message="已删除")


@router.post("/{node_id}/connect", response_model=ComputeNodeResponse)
async def connect_node(
    node_id: str,
    connect_config: ComputeNodeConnect | None = None,
    db: AsyncSession = Depends(get_db),
):
    """连接算力节点 — 自动检测 GPU/CPU/RAM 硬件信息

    本机节点：直接检测
    远程节点：通过 SSH 连接检测
    """
    node = await db.get(ComputeNode, node_id)
    if not node:
        raise HTTPException(404, "算力节点不存在")

    # 更新连接配置
    if connect_config and node.node_type == "remote_ssh":
        node.ssh_user = connect_config.ssh_user or node.ssh_user
        node.ssh_key_path = connect_config.ssh_key_path or node.ssh_key_path
        node.ssh_port = connect_config.ssh_port or node.ssh_port
        node.python_path = connect_config.python_path or node.python_path
        node.working_dir = connect_config.working_dir or node.working_dir

    logger.info(f"Connecting compute node: {node.name} ({node.node_type})")

    try:
        if node.node_type == "local":
            hw = full_detect("local")
        else:
            ssh_target = f"{node.ssh_user}@{node.host}" if node.ssh_user else node.host
            hw = full_detect(
                "remote_ssh",
                ssh_target=ssh_target,
                ssh_key=node.ssh_key_path or "",
                ssh_port=node.ssh_port,
            )

        # 写入硬件信息
        gpu = hw["gpu"]
        node.gpu_count = gpu["count"]
        node.gpu_model = gpu["model"]
        node.gpu_total_vram_gb = gpu["total_vram_gb"]
        node.cuda_version = gpu["cuda_version"]
        node.cpu_count = hw["cpu"]["count"]
        node.ram_total_gb = hw["ram"]["total_gb"]

        # 实时状态
        gs = hw["gpu_stats"]
        node.gpu_utilization = gs["utilization"]
        node.gpu_vram_used_gb = gs["vram_used_gb"]
        node.gpu_temp = gs["temp"]
        node.cpu_utilization = hw.get("cpu_util", 0.0)
        node.ram_used_gb = hw["ram"]["used_gb"]
        node.disk_free_gb = hw["disk_free_gb"]

        # 更新状态
        node.status = "online"
        node.connected_at = datetime.utcnow()
        node.last_heartbeat = datetime.utcnow()

        logger.info(f"Node {node.name} connected: {node.gpu_count} GPU(s), {node.cpu_count} CPU, {node.ram_total_gb}GB RAM")

    except Exception as e:
        logger.error(f"Failed to connect node {node.name}: {e}")
        node.status = "error"
        raise HTTPException(500, f"连接失败: {e}")

    return node


@router.post("/{node_id}/disconnect")
async def disconnect_node(node_id: str, db: AsyncSession = Depends(get_db)):
    """断开算力节点"""
    node = await db.get(ComputeNode, node_id)
    if not node:
        raise HTTPException(404, "算力节点不存在")
    node.status = "offline"
    node.connected_at = None
    return ApiResponse(message="已断开")


@router.post("/{node_id}/heartbeat", response_model=GpuStatsResponse)
async def heartbeat(node_id: str, db: AsyncSession = Depends(get_db)):
    """心跳 + 实时资源监控

    前端定时调用（每 5 秒）获取最新 GPU/CPU/RAM 利用率
    """
    node = await db.get(ComputeNode, node_id)
    if not node:
        raise HTTPException(404, "算力节点不存在")
    if node.status == "offline":
        raise HTTPException(400, "节点未连接")

    try:
        if node.node_type == "local":
            gs = get_gpu_stats()
            cpu_util = get_cpu_stats()
            ram = detect_ram()
            disk = get_disk_free("/")
        else:
            from app.engine.compute_detector import _run_remote_cmd
            ssh_target = f"{node.ssh_user}@{node.host}" if node.ssh_user else node.host
            raw = _run_remote_cmd(ssh_target,
                "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu "
                "--format=csv,noheader,nounits", ssh_key=node.ssh_key_path or "", port=node.ssh_port)
            parts = [p.strip() for p in raw.split("\n")[0].split(",")] if raw else []
            gs = {
                "utilization": float(parts[0]) if len(parts) >= 4 else 0,
                "vram_used_gb": round(float(parts[1]) / 1024, 2) if len(parts) >= 4 else 0,
                "vram_total_gb": round(float(parts[2]) / 1024, 2) if len(parts) >= 4 else 0,
                "temp": float(parts[3]) if len(parts) >= 4 else 0,
            }
            cpu_util = 0.0
            ram = {"used_gb": 0, "total_gb": node.ram_total_gb}
            disk = 0.0

        # 更新实时数据
        node.gpu_utilization = gs["utilization"]
        node.gpu_vram_used_gb = gs["vram_used_gb"]
        node.gpu_temp = gs["temp"]
        node.cpu_utilization = cpu_util
        node.ram_used_gb = ram["used_gb"]
        node.disk_free_gb = disk
        node.last_heartbeat = datetime.utcnow()

        return GpuStatsResponse(
            gpu_utilization=gs["utilization"],
            gpu_vram_used_gb=gs["vram_used_gb"],
            gpu_vram_total_gb=gs.get("vram_total_gb", node.gpu_total_vram_gb),
            gpu_temp=gs["temp"],
            cpu_utilization=cpu_util,
            ram_used_gb=ram["used_gb"],
            ram_total_gb=node.ram_total_gb,
            disk_free_gb=disk,
        )
    except Exception as e:
        logger.error(f"Heartbeat failed for {node.name}: {e}")
        node.status = "error"
        raise HTTPException(500, f"心跳失败: {e}")


@router.post("/auto-connect-local")
async def auto_connect_local(db: AsyncSession = Depends(get_db)):
    """一键自动检测本机算力并注册连接

    自动创建/更新本机节点，检测硬件后直接变为 online
    """
    # 查找已有的本机节点
    result = await db.execute(
        select(ComputeNode).where(ComputeNode.node_type == "local").limit(1)
    )
    node = result.scalars().first()

    if not node:
        node = ComputeNode(
            name="本机算力",
            node_type="local",
            host="localhost",
        )
        db.add(node)
        await db.flush()

    # 直接复用 connect 逻辑
    hw = full_detect("local")
    gpu = hw["gpu"]
    node.gpu_count = gpu["count"]
    node.gpu_model = gpu["model"]
    node.gpu_total_vram_gb = gpu["total_vram_gb"]
    node.cuda_version = gpu["cuda_version"]
    node.cpu_count = hw["cpu"]["count"]
    node.ram_total_gb = hw["ram"]["total_gb"]

    gs = hw["gpu_stats"]
    node.gpu_utilization = gs["utilization"]
    node.gpu_vram_used_gb = gs["vram_used_gb"]
    node.gpu_temp = gs["temp"]
    node.cpu_utilization = hw.get("cpu_util", 0.0)
    node.ram_used_gb = hw["ram"]["used_gb"]
    node.disk_free_gb = hw["disk_free_gb"]
    node.status = "online"
    node.connected_at = datetime.utcnow()
    node.last_heartbeat = datetime.utcnow()

    return {
        "node_id": node.id,
        "name": node.name,
        "status": "online",
        "gpu_count": node.gpu_count,
        "gpu_model": node.gpu_model,
        "gpu_vram_gb": node.gpu_total_vram_gb,
        "cpu_count": node.cpu_count,
        "ram_gb": node.ram_total_gb,
        "cuda_version": node.cuda_version,
        "message": f"已连接: {node.gpu_count} GPU, {node.cpu_count} CPU, {node.ram_total_gb}GB RAM",
    }


@router.get("/available/list")
async def list_available_nodes(db: AsyncSession = Depends(get_db)):
    """列出所有 online 状态的可用算力节点"""
    result = await db.execute(
        select(ComputeNode).where(ComputeNode.status == "online")
    )
    nodes = result.scalars().all()
    return {
        "count": len(nodes),
        "total_gpus": sum(n.gpu_count for n in nodes),
        "total_vram_gb": sum(n.gpu_total_vram_gb for n in nodes),
        "nodes": [
            {"id": n.id, "name": n.name, "gpu_count": n.gpu_count, "gpu_model": n.gpu_model}
            for n in nodes
        ],
    }
