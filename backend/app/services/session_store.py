"""会话存储。

Redis 为权威源；``SessionStore`` 是注入缝隙，测试可用 fakeredis 替换。
载荷极简（身份可由 DB 重建）：``user_id`` + ``issued_at`` + 版本号。角色/姓名/
must_change_password 不缓存——每次鉴权从 DB 取最新值。
"""

from __future__ import annotations

import time
from typing import Protocol

import redis.asyncio as redis
from pydantic import BaseModel

from app.core.security import generate_session_token


class SessionData(BaseModel):
    user_id: int
    issued_at: int  # epoch seconds
    v: int = 1


class SessionStore(Protocol):
    async def create(self, user_id: int) -> str: ...
    async def get(self, sid: str) -> SessionData | None: ...
    async def delete(self, sid: str) -> None: ...


def _key(sid: str) -> str:
    return f"session:{sid}"


class RedisSessionStore:
    """基于 redis.asyncio 的会话存储。``client`` 可为真 Redis 或 fakeredis。"""

    def __init__(self, client: redis.Redis, ttl: int) -> None:
        self._client = client
        self._ttl = ttl

    async def create(self, user_id: int) -> str:
        sid = generate_session_token()
        data = SessionData(user_id=user_id, issued_at=int(time.time()))
        await self._client.set(_key(sid), data.model_dump_json(), ex=self._ttl)
        return sid

    async def get(self, sid: str) -> SessionData | None:
        raw = await self._client.get(_key(sid))
        if raw is None:
            return None
        return SessionData.model_validate_json(raw)

    async def delete(self, sid: str) -> None:
        await self._client.delete(_key(sid))
