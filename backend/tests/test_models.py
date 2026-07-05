"""ORM 模型测试"""
import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_create_model(db_session):
    """测试创建模型记录"""
    from app.models import Model, ModelType

    model = Model(
        name="test-glm-4",
        model_type=ModelType.TEACHER,
        base_model="THUDM/glm-4-9b-chat",
        parameters=9,
        description="测试模型",
    )
    db_session.add(model)
    await db_session.flush()

    assert model.id is not None
    assert model.name == "test-glm-4"
    assert model.model_type == ModelType.TEACHER


@pytest.mark.asyncio
async def test_create_dataset(db_session):
    """测试创建数据集"""
    from app.models import Dataset

    ds = Dataset(
        name="test-dataset",
        description="测试数据集",
        format="jsonl",
        num_samples=100,
        file_path="datasets/test/test.jsonl",
        file_size=10240,
    )
    db_session.add(ds)
    await db_session.flush()

    assert ds.id is not None
    assert ds.num_samples == 100
