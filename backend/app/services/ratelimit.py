"""基于 Redis 的固定窗口限流（选课操作）。"""

from __future__ import annotations

import redis.asyncio as redis

DEFAULT_LIMIT = 20  # 窗口内最大选课尝试次数
DEFAULT_WINDOW = 60  # 窗口大小（秒）


async def check_rate_limit(
    client: redis.Redis,
    user_id: int,
    limit: int = DEFAULT_LIMIT,
    window: int = DEFAULT_WINDOW,
) -> bool:
    """返回 True 表示未超限；False 表示超限。

    固定窗口：首次请求 ``INCR=1`` 时设置 ``EXPIRE``，窗口内累计超过 ``limit`` 即拒绝。
    """
    key = f"ratelimit:enroll:{user_id}"
    count = await client.incr(key)
    if count == 1:
        await client.expire(key, window)
    return count <= limit
