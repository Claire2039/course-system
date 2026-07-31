"""最小通知：落库 + Redis pub/sub。

落库随当前事务 commit；发布 best-effort（失败仅告警），供 M5 SSE 消费。
SPEC §3.3 频道 ``notify:ch:{user_id}``。
"""

from __future__ import annotations

import json
import logging

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification

logger = logging.getLogger(__name__)


async def notify(
    session: AsyncSession, user_id: int, type: str, payload: dict
) -> None:
    """落库一条通知（随外层事务一起提交）。"""
    session.add(Notification(user_id=user_id, type=type, payload=payload))


async def publish_event(
    client: redis.Redis | None, user_id: int, type: str, payload: dict
) -> None:
    """best-effort 发布事件到 Redis 频道。"""
    if client is None:
        return
    try:
        await client.publish(
            f"notify:ch:{user_id}",
            json.dumps({"type": type, "payload": payload}, default=str),
        )
    except Exception:
        logger.warning("redis publish failed (user=%s)", user_id, exc_info=True)
