"""InMemoryStorage CRUD 单测（验证存储抽象契约；MinioStorage 由 compose 端到端验证）。"""

import pytest

from app.services.storage import InMemoryStorage


async def test_put_get_delete() -> None:
    s = InMemoryStorage()
    await s.put("k1", b"hello", "text/plain")
    assert await s.get("k1") == b"hello"
    await s.delete("k1")
    with pytest.raises(KeyError):
        await s.get("k1")


async def test_get_missing_raises() -> None:
    s = InMemoryStorage()
    with pytest.raises(KeyError):
        await s.get("nope")


async def test_delete_missing_is_idempotent() -> None:
    s = InMemoryStorage()
    await s.delete("nope")  # 不抛
