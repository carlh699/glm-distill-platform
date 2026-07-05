.PHONY: help install-dev install-prod dev-backend dev-frontend dev-worker docker-up docker-down test lint format

help:
	@echo "GLM Distill Platform - 开发命令"
	@echo ""
	@echo "  make install-dev     安装开发依赖 (前后端)"
	@echo "  make dev-backend     启动后端 (FastAPI + reload)"
	@echo "  make dev-frontend    启动前端 (Vite dev server)"
	@echo "  make dev-worker      启动 Celery worker"
	@echo "  make docker-up       启动全部 Docker 服务"
	@echo "  make docker-down     停止全部 Docker 服务"
	@echo "  make test            运行测试"
	@echo "  make lint            代码检查"

install-dev:
	cd frontend && npm install
	pip install -r requirements.txt

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

dev-worker:
	cd backend && celery -A app.celery_app worker --loglevel=info --concurrency=2 -Q training,evaluation,generation

dev-flower:
	cd backend && celery -A app.celery_app flower --port=5555

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose up -d --build

docker-logs:
	docker compose logs -f

test:
	cd backend && python -m pytest tests/ -v

lint:
	cd backend && python -m flake8 app/ --max-line-length=120
	cd frontend && npm run lint 2>/dev/null || true

format:
	cd backend && python -m black app/ && python -m isort app/
