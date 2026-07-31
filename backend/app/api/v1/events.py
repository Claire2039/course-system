"""SSE 实时通知：``GET /events``。

订阅 Redis 频道 ``notify:ch:{user_id}``，把事件流推给浏览器 EventSource。
用 ``get_current_user_id``（轻量、不持有 DB 连接）避免长连接占用数据库连接池。
Caddy 已对 ``/events*`` 设置 ``flush_interval -1``（M0），流式不缓冲。
"""

from __future__ import annotations

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user_id
from app.core.redis import get_redis

router = APIRouter()


@router.get("/events")
async def events(
    user_id: int = Depends(get_current_user_id),
    client: redis.Redis = Depends(get_redis),
) -> EventSourceResponse:
    channel = f"notify:ch:{user_id}"

    async def gen():
        ps = client.pubsub()
        await ps.subscribe(channel)
        try:
            async for msg in ps.listen():
                if msg["type"] == "message":
                    # data 已是 JSON 字符串（decode_responses=True）
                    yield {"event": "message", "data": msg["data"]}
        finally:
            await ps.unsubscribe(channel)
            await ps.aclose()

    return EventSourceResponse(gen())
