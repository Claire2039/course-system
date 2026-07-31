"""FastAPI 应用入口。

M2：接入 Redis 客户端生命周期、挂载 /api/v1 业务路由、就绪探针同时探测 DB 与 Redis。
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import settings
from app.core.redis import create_redis_client
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Redis 客户端惰性创建（不建连）；关闭时一并释放。
    app.state.redis = create_redis_client()
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await engine.dispose()


app = FastAPI(
    title="Course Registration API",
    version="0.2.0",
    description="学校选课系统后端。详见 SPEC.md。",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """存活探针：进程在跑即 OK，不依赖任何外部服务。"""
    return {"status": "ok", "service": "course-api", "environment": settings.environment}


@app.get("/health/ready", tags=["meta"])
async def readiness(request: Request) -> dict:
    """就绪探针：DB 与 Redis 均连通即就绪；任一不可达或超时则 503。"""
    try:
        await asyncio.wait_for(
            asyncio.gather(_ping_db(), _ping_redis(request.app)),
            timeout=3,
        )
    except Exception:
        raise HTTPException(status_code=503, detail={"status": "unhealthy"})
    return {"status": "ready", "db": "ok", "redis": "ok"}


async def _ping_db() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _ping_redis(app: FastAPI) -> None:
    client = getattr(app.state, "redis", None)
    if client is None:
        raise RuntimeError("redis client not initialized")
    await client.ping()
