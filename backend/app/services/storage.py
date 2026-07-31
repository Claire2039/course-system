"""对象存储抽象（MinIO / S3 兼容）。

``minio`` SDK 是同步的，用 ``asyncio.to_thread`` 包裹；测试用 ``InMemoryStorage``
（通过覆盖 ``get_storage`` 依赖注入，无需真 MinIO）。

``file_key`` 是存储内部标识，**绝不直接返回给客户端**——下载走鉴权后的 API 流式端点。
"""

from __future__ import annotations

import asyncio
import io
from typing import Protocol

from app.core.config import settings


class StorageClient(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


class MinioStorage:
    """同步 minio SDK 的异步封装。构造不建连，put/get 时才连。"""

    def __init__(self) -> None:
        from minio import Minio

        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket = settings.minio_bucket

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            self._bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    async def get(self, key: str) -> bytes:
        def _read() -> bytes:
            resp = self._client.get_object(self._bucket, key)
            try:
                return resp.read()
            finally:
                resp.close()
                resp.release_conn()

        return await asyncio.to_thread(_read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.remove_object, self._bucket, key)


class InMemoryStorage:
    """测试用：进程内字典实现。"""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self._store[key] = data

    async def get(self, key: str) -> bytes:
        if key not in self._store:
            raise KeyError(key)
        return self._store[key]

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
