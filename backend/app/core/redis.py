"""异步 Redis 客户端与依赖。

客户端在 ``main.lifespan`` 中创建并挂到 ``app.state.redis``，关闭时 ``aclose``。
``decode_responses=True``：本系统只存 JSON 字符串，省去 bytes 解码。
"""

from __future__ import annotations

import redis.asyncio as redis
from fastapi import Request

from app.core.config import settings


def create_redis_client() -> redis.Redis:
    """构建异步 Redis 客户端（不立即建连）。供 lifespan 调用。"""
    return redis.from_url(settings.redis_url, decode_responses=True)


def get_redis(request: Request) -> redis.Redis:
    """FastAPI 依赖：取 lifespan 挂载的客户端。"""
    return request.app.state.redis
