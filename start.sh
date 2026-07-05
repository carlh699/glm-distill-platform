#!/bin/bash
# GLM Distill Platform - 快速启动脚本
set -e

echo "=== GLM Distill Platform - 快速启动 ==="

# 1. 检查 .env
if [ ! -f .env ]; then
    echo "[1/5] 创建 .env 配置文件..."
    cp .env.example .env
    echo "请编辑 .env 填写 ZHIPU_API_KEY 等配置后重新运行"
    exit 1
fi

# 2. 启动基础设施
echo "[2/5] 启动基础设施 (PostgreSQL, Redis, MinIO, MLflow)..."
docker compose up -d postgres redis minio mlflow

# 等待健康检查
echo "等待服务就绪..."
sleep 10

# 3. 启动后端
echo "[3/5] 启动 FastAPI 后端..."
docker compose up -d api worker flower

# 4. 构建并启动前端
echo "[4/5] 构建并启动 Vue3 前端..."
docker compose up -d --build web

# 5. 检查状态
echo "[5/5] 检查服务状态..."
docker compose ps

echo ""
echo "=== 启动完成 ==="
echo "Web UI:    http://localhost:3000"
echo "API Docs:  http://localhost:8000/docs"
echo "MLflow:    http://localhost:5000"
echo "MinIO:     http://localhost:9001 (minioadmin/minioadmin123)"
echo "Flower:    http://localhost:5555"
