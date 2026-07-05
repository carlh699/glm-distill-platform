"""Pytest 配置"""
import os
import sys
import pytest
import pytest_asyncio

# 添加 backend 目录到 sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 测试用 SQLite 内存数据库
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"


@pytest_asyncio.fixture
async def db_session():
    """测试用数据库 session"""
    from app.database import engine, async_session, Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client():
    """测试用 FastAPI 客户端"""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    import asyncio

    transport = ASGITransport(app=app)
    return asyncio.run(AsyncClient(transport=transport, base_url="http://test").aclose()) or \
           asyncio.run(AsyncClient(transport=transport, base_url="http://test").__aenter__())
