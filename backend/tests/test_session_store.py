"""RedisSessionStore CRUD 测试，使用 fakeredis（无需真 Redis）。"""

import pytest
import fakeredis.aioredis

from app.services.session_store import RedisSessionStore


@pytest.fixture
def store() -> RedisSessionStore:
    # decode_responses=True 与生产端 create_redis_client 一致
    return RedisSessionStore(fakeredis.aioredis.FakeRedis(decode_responses=True), ttl=3600)


async def test_create_get_delete(store: RedisSessionStore) -> None:
    sid = await store.create(42)
    data = await store.get(sid)
    assert data is not None
    assert data.user_id == 42
    assert data.v == 1

    await store.delete(sid)
    assert await store.get(sid) is None


async def test_get_unknown_returns_none(store: RedisSessionStore) -> None:
    assert await store.get("does-not-exist") is None


async def test_create_sets_ttl(store: RedisSessionStore) -> None:
    sid = await store.create(7)
    ttl = await store._client.ttl(f"session:{sid}")
    assert ttl > 0


async def test_different_users_get_different_sids(store: RedisSessionStore) -> None:
    s1 = await store.create(1)
    s2 = await store.create(2)
    assert s1 != s2
