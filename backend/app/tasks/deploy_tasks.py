"""模型部署 Celery 任务"""
import subprocess
import os
from datetime import datetime
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.celery_app import app
from app.config import settings

# ─── 同步数据库连接 (懒加载) ───
SYNC_DB_URL = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2").replace("aiosqlite", "psycopg2")
_sync_engine = None
SyncSession = None


def _get_sync_session():
    global _sync_engine, SyncSession
    if _sync_engine is None:
        _sync_engine = create_engine(SYNC_DB_URL, pool_size=5)
        SyncSession = sessionmaker(bind=_sync_engine)
    return SyncSession()


def _get_deployment(dep_id: str):
    with _get_sync_session() as db:
        result = db.execute(text("SELECT * FROM deployments WHERE id = :id"), {"id": dep_id})
        return dict(result.mappings().first())


def _update_deployment(dep_id: str, **fields):
    with _get_sync_session() as db:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        db.execute(text(f"UPDATE deployments SET {sets} WHERE id = :id"), {"id": dep_id, **fields})
        db.commit()


@app.task(name="app.tasks.deploy_tasks.run_deployment")
def run_deployment(dep_id: str):
    """使用 vLLM 部署模型"""
    logger.info(f"[Celery] Starting deployment: {dep_id}")

    dep = _get_deployment(dep_id)
    if not dep:
        return {"error": "deployment not found"}

    model_path = dep["model_path"]
    framework = dep.get("framework", "vllm")

    try:
        from app.services.storage import MinIOClient
        minio_client = MinIOClient()

        local_model_dir = f"/data/models/deploy_{dep_id}"
        os.makedirs(local_model_dir, exist_ok=True)

        if "/" in model_path:
            bucket, prefix = model_path.split("/", 1)
            for obj in minio_client.list_objects(bucket, prefix=prefix):
                rel = obj.object_name[len(prefix):].lstrip("/")
                local_file = os.path.join(local_model_dir, rel)
                os.makedirs(os.path.dirname(local_file), exist_ok=True)
                minio_client.download_file(bucket, obj.object_name, local_file)
            deploy_path = local_model_dir
        else:
            deploy_path = model_path

        if framework == "vllm":
            port = _find_free_port()
            cmd = [
                "python", "-m", "vllm.entrypoints.openai.api_server",
                "--model", deploy_path, "--port", str(port),
                "--trust-remote-code", "--dtype", "half",
            ]
            env = os.environ.copy()
            env["VLLM_NO_USAGE_STATS"] = "1"
            proc = subprocess.Popen(cmd, env=env,
                stdout=open(f"/tmp/vllm_{dep_id}.log", "w"),
                stderr=subprocess.STDOUT)

            endpoint = f"http://localhost:{port}/v1"
            _update_deployment(dep_id, status="running", endpoint_url=endpoint,
                config={"pid": proc.pid, "port": port})
            logger.info(f"vLLM deployed at {endpoint} (PID={proc.pid})")
            return {"deployment_id": dep_id, "endpoint": endpoint, "pid": proc.pid}

        elif framework == "transformers":
            port = _find_free_port()
            endpoint = f"http://localhost:{port}/v1"
            _update_deployment(dep_id, status="running", endpoint_url=endpoint)
            return {"deployment_id": dep_id, "endpoint": endpoint}

    except Exception as e:
        logger.exception(f"Deployment failed: {e}")
        _update_deployment(dep_id, status="failed")
        raise


def _find_free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]
