"""共享 pytest 夹具。

``auth_db``：为认证/管理集成测试准备一个临时 Postgres（建表）+ fakeredis 会话存储，
并覆盖 ``get_session`` / ``get_session_store`` 依赖。无 ``TEST_DATABASE_URL`` 时跳过。
真正的 Redis 不是必需的——会话走 fakeredis。
"""

import os

import fakeredis.aioredis
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_session_store, get_storage
from app.core.redis import get_redis
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.services.session_store import RedisSessionStore
from app.services.storage import InMemoryStorage

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest_asyncio.fixture
async def auth_db():
    if not TEST_DATABASE_URL:
        pytest.skip("needs TEST_DATABASE_URL")
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_session():
        async with Session() as s:
            yield s

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    def _get_store() -> RedisSessionStore:
        return RedisSessionStore(fake, ttl=3600)

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[get_session_store] = _get_store
    app.dependency_overrides[get_redis] = lambda: fake
    storage = InMemoryStorage()
    app.dependency_overrides[get_storage] = lambda: storage
    try:
        yield Session
    finally:
        app.dependency_overrides.clear()
        await fake.aclose()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
