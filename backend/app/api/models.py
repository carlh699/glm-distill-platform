"""Models CRUD API - 模型仓库管理"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import Model, ModelType
from app.schemas import ModelCreate, ModelResponse, ApiResponse

router = APIRouter(prefix="/models", tags=["模型管理"])


@router.get("", response_model=list[ModelResponse])
async def list_models(
    model_type: ModelType | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Model)
    if model_type:
        query = query.where(Model.model_type == model_type)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=ModelResponse, status_code=201)
async def create_model(data: ModelCreate, db: AsyncSession = Depends(get_db)):
    model = Model(**data.model_dump())
    db.add(model)
    await db.flush()
    return model


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(model_id: str, db: AsyncSession = Depends(get_db)):
    model = await db.get(Model, model_id)
    if not model:
        raise HTTPException(404, "模型不存在")
    return model


@router.delete("/{model_id}")
async def delete_model(model_id: str, db: AsyncSession = Depends(get_db)):
    model = await db.get(Model, model_id)
    if not model:
        raise HTTPException(404, "模型不存在")
    await db.delete(model)
    return ApiResponse(message="已删除")


@router.get("/presets/list")
async def list_preset_models():
    """预置 GLM 模型列表"""
    return [
        {"name": "GLM-4-Plus (API)", "base_model": "glm-4-plus", "type": "teacher",
         "parameters": 300, "source": "zhipu_api", "description": "智谱 GLM-4 Plus 旗舰模型（API 调用）"},
        {"name": "GLM-4-9B-Chat", "base_model": "THUDM/glm-4-9b-chat", "type": "teacher",
         "parameters": 9, "source": "huggingface", "description": "GLM-4 9B 开源对话模型"},
        {"name": "GLM-4-9B", "base_model": "THUDM/glm-4-9b", "type": "teacher",
         "parameters": 9, "source": "huggingface", "description": "GLM-4 9B 基座模型"},
        {"name": "GLM-5 (API)", "base_model": "glm-5", "type": "teacher",
         "parameters": 300, "source": "zhipu_api", "description": "智谱 GLM-5 最新旗舰模型（API）"},
        {"name": "ChatGLM3-6B", "base_model": "THUDM/chatglm3-6b", "type": "student",
         "parameters": 6, "source": "huggingface", "description": "ChatGLM3 6B 对话模型，常用蒸馏学生模型"},
        {"name": "ChatGLM3-6B-INT4", "base_model": "THUDM/chatglm3-6b-int4", "type": "student",
         "parameters": 6, "source": "huggingface", "description": "ChatGLM3 6B 量化版本，4-bit 推理"},
        {"name": "GLM-4-9B-Chat-INT4", "base_model": "THUDM/glm-4-9b-chat-int4", "type": "student",
         "parameters": 9, "source": "huggingface", "description": "GLM-4 9B 量化版本"},
        {"name": "GLM-Edge-1.5B", "base_model": "THUDM/glm-edge-1.5b", "type": "student",
         "parameters": 2, "source": "huggingface", "description": "GLM Edge 1.5B 轻量模型，适合端侧部署"},
    ]
