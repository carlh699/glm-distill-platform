"""扩展 API 端点测试"""
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db_client(db_session):
    """使用测试数据库的异步 API 客户端"""
    from httpx import ASGITransport, AsyncClient
    from app.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_new_model_fields_have_defaults(db_session):
    """测试评估和部署新增字段默认值"""
    from app.models import Deployment, Evaluation

    evaluation = Evaluation(task_id="task-1", model_path="/models/student")
    deployment = Deployment(model_name="student", model_path="/models/student")

    db_session.add_all([evaluation, deployment])
    await db_session.flush()

    assert evaluation.teacher_metrics == {}
    assert deployment.health_status == "unknown"


@pytest.mark.asyncio
async def test_dataset_stats_and_preprocess_endpoints(db_session, db_client):
    """测试数据集统计和预处理端点"""
    from app.models import Dataset

    dataset = Dataset(
        name="raw-samples",
        description="测试数据集",
        format="jsonl",
        num_samples=4,
        file_path="datasets/raw-samples/data.jsonl",
        file_size=400,
        columns={"prompt": "string", "answer": "string"},
        tags=[],
    )
    db_session.add(dataset)
    await db_session.flush()

    stats_resp = await db_client.get(f"/api/v1/datasets/{dataset.id}/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["code"] == 200
    assert stats["data"]["num_samples"] == 4
    assert stats["data"]["column_count"] == 2
    assert stats["data"]["average_sample_size"] == 100.0

    preprocess_resp = await db_client.post(f"/api/v1/datasets/{dataset.id}/preprocess")
    assert preprocess_resp.status_code == 200
    processed = preprocess_resp.json()
    assert processed["code"] == 200
    assert processed["data"]["status"] == "preprocessed"

    await db_session.refresh(dataset)
    assert "preprocessed" in dataset.tags


@pytest.mark.asyncio
async def test_evaluation_compare_and_leaderboard_endpoints(db_session, db_client):
    """测试评估对比和排行榜端点"""
    from app.models import Evaluation

    baseline = Evaluation(
        task_id="task-a",
        model_path="/models/baseline",
        accuracy=0.72,
        perplexity=11.5,
        teacher_metrics={"accuracy": 0.90},
    )
    candidate = Evaluation(
        task_id="task-b",
        model_path="/models/candidate",
        accuracy=0.84,
        perplexity=8.2,
        teacher_metrics={"accuracy": 0.91},
    )
    db_session.add_all([baseline, candidate])
    await db_session.flush()

    compare_resp = await db_client.post(
        "/api/v1/evaluations/compare",
        json={"evaluation_ids": [baseline.id, candidate.id]},
    )
    assert compare_resp.status_code == 200
    comparison = compare_resp.json()
    assert comparison["code"] == 200
    assert [item["id"] for item in comparison["data"]["items"]] == [baseline.id, candidate.id]
    assert comparison["data"]["items"][0]["teacher_metrics"] == {"accuracy": 0.90}
    assert comparison["data"]["best"]["accuracy"]["evaluation_id"] == candidate.id
    assert comparison["data"]["best"]["perplexity"]["evaluation_id"] == candidate.id

    leaderboard_resp = await db_client.get("/api/v1/evaluations/leaderboard?metric=accuracy")
    assert leaderboard_resp.status_code == 200
    leaderboard = leaderboard_resp.json()
    assert leaderboard["code"] == 200
    assert leaderboard["data"][0]["evaluation_id"] == candidate.id
    assert leaderboard["data"][0]["metric_value"] == 0.84


@pytest.mark.asyncio
async def test_deployment_status_and_scale_endpoints(db_session, db_client):
    """测试部署状态和扩缩容端点"""
    from app.models import Deployment

    deployment = Deployment(
        model_name="student",
        model_path="/models/student",
        status="running",
        replicas=1,
        gpu_memory_gb=12.5,
    )
    db_session.add(deployment)
    await db_session.flush()

    status_resp = await db_client.get(f"/api/v1/deployments/{deployment.id}/status")
    assert status_resp.status_code == 200
    status = status_resp.json()
    assert status["code"] == 200
    assert status["data"]["status"] == "running"
    assert status["data"]["health_status"] == "unknown"
    assert status["data"]["replicas"] == 1

    scale_resp = await db_client.post(
        f"/api/v1/deployments/{deployment.id}/scale",
        json={"replicas": 3},
    )
    assert scale_resp.status_code == 200
    scaled = scale_resp.json()
    assert scaled["code"] == 200
    assert scaled["data"]["replicas"] == 3

    await db_session.refresh(deployment)
    assert deployment.replicas == 3
