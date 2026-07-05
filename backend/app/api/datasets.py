"""Datasets API - 数据集管理"""
import io
import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Dataset
from app.schemas import DatasetResponse, ApiResponse
from app.services.storage import MinIOClient
from app.config import settings

router = APIRouter(prefix="/datasets", tags=["数据集管理"])


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Dataset).offset((page - 1) * page_size).limit(page_size)
    )
    return result.scalars().all()


@router.post("", response_model=DatasetResponse, status_code=201)
async def create_dataset(
    name: str,
    description: str = "",
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """上传并创建数据集"""
    content = await file.read()
    file_size = len(content)

    # 解析统计
    num_samples = 0
    columns = {}
    fmt = file.filename.split(".")[-1] if file.filename else "jsonl"

    if fmt == "jsonl":
        for line in content.decode("utf-8").strip().split("\n"):
            if line.strip():
                obj = json.loads(line)
                num_samples += 1
                for k in obj:
                    columns[k] = columns.get(k, "string")
    elif fmt == "csv":
        lines = content.decode("utf-8").strip().split("\n")
        num_samples = max(0, len(lines) - 1)
        if lines:
            columns = {c.strip(): "string" for c in lines[0].split(",")}

    # 上传到 MinIO
    minio_client = MinIOClient()
    object_name = f"datasets/{name}/{file.filename}"
    minio_client.upload_bytes(settings.MINIO_BUCKET_DATASETS, object_name, content, file.content_type)

    dataset = Dataset(
        name=name,
        description=description,
        format=fmt,
        num_samples=num_samples,
        file_path=f"{settings.MINIO_BUCKET_DATASETS}/{object_name}",
        file_size=file_size,
        columns=columns,
    )
    db.add(dataset)
    await db.flush()
    return dataset


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, "数据集不存在")
    return dataset


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, "数据集不存在")
    await db.delete(dataset)
    return ApiResponse(message="已删除")


@router.get("/{dataset_id}/preview")
async def preview_dataset(dataset_id: str, n: int = 10, db: AsyncSession = Depends(get_db)):
    """预览数据集前 N 条"""
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, "数据集不存在")

    minio_client = MinIOClient()
    bucket, obj_name = dataset.file_path.split("/", 1)
    content = minio_client.download_bytes(bucket, obj_name)

    samples = []
    for i, line in enumerate(content.decode("utf-8").strip().split("\n")):
        if i >= n:
            break
        try:
            samples.append(json.loads(line))
        except json.JSONDecodeError:
            samples.append({"raw": line[:500]})

    return {"total": dataset.num_samples, "samples": samples}
