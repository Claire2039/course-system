"""异步数据库引擎与会话工厂。

M1：仅引擎与会话；业务代码在 M2+ 通过 ``get_session`` 依赖注入使用。
``create_async_engine`` 在导入期**不建立连接**（惰性），故即便 DB 不可用，本模块与
``app.main`` 仍可正常导入、``/health`` 仍可用。
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"timeout": 5},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：每请求一会话，请求结束自动关闭。"""
    async with AsyncSessionLocal() as session:
        yield session
