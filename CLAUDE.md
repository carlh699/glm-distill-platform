# GLM Distill Platform - CLAUDE.md / AGENTS.md
# 供 Claude Code / Codex CLI 使用

## 项目概述
基于智谱 GLM 系列大模型的蒸馏 MLOps 平台。

## 架构
- **前端**: Vue3 + Element Plus + ECharts (`frontend/`)
- **后端**: FastAPI + SQLAlchemy async + Pydantic (`backend/app/`)
- **任务队列**: Celery + Redis (`backend/app/tasks/`)
- **训练引擎**: PyTorch + HuggingFace Transformers + DeepSpeed (`backend/app/engine/`)
- **存储**: PostgreSQL (元数据) + MinIO (模型文件) + MLflow (实验追踪)
- **部署**: Docker Compose (8 services)

## 关键路径
- 后端入口: `backend/app/main.py`
- ORM 模型: `backend/app/models.py`
- API 路由: `backend/app/api/`
- 蒸馏引擎: `backend/app/engine/distillation.py`
- Celery 配置: `backend/app/celery_app.py`
- 前端入口: `frontend/src/main.js`
- 前端路由: `frontend/src/router/index.js`

## 开发命令
- `make dev-backend` — 启动 FastAPI (端口 8000)
- `make dev-frontend` — 启动 Vite (端口 3000)
- `make dev-worker` — 启动 Celery worker
- `make docker-up` — 启动全部 Docker 服务

## 代码规范
- Python: 4 空格缩进, 行宽 120
- Vue: 2 空格缩进, Composition API (`<script setup>`)
- 所有 API 响应包裹在 `{code, message, data}` 中
- DB session 通过 `Depends(get_db)` 注入

## 环境变量
见 `.env.example`，关键字段:
- `ZHIPU_API_KEY` — 智谱 API Key
- `DATABASE_URL` — PostgreSQL 连接串
- `CELERY_BROKER_URL` — Redis 连接串
- `MINIO_ENDPOINT` — MinIO 地址

## 数据库
- 开发环境: `init_db()` 自动建表
- 生产环境: 使用 Alembic 迁移 (`alembic/`)
- 5 张核心表: models, datasets, distill_tasks, evaluations, deployments
