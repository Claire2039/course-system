"""认证与鉴权依赖。

依赖链：``get_current_user``（401）→ ``require_password_changed``（403 must_change_password）
→ ``require_role(*roles)``（403 forbidden）。业务路由用 ``require_role`` 即同时获得改密校验。
"""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import get_session
from app.models import User
from app.models.constants import UserRole
from app.services.session_store import RedisSessionStore, SessionStore
from app.services.storage import MinioStorage, StorageClient

_storage_singleton: StorageClient | None = None


def get_storage() -> StorageClient:
    """对象存储依赖（懒构造 MinioStorage；测试覆盖为 InMemoryStorage）。"""
    global _storage_singleton
    if _storage_singleton is None:
        _storage_singleton = MinioStorage()
    return _storage_singleton


def get_session_store(request: Request) -> SessionStore:
    """从 lifespan 挂载的 Redis 客户端构建会话存储（测试可 override 为 fakeredis）。"""
    return RedisSessionStore(request.app.state.redis, settings.session_ttl_seconds)


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    store: SessionStore = Depends(get_session_store),
    token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> User:
    """cookie → 会话 → DB 用户；任一环节失败即 401。"""
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthenticated", "message": "未登录。"},
        )
    data = await store.get(token)
    if data is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthenticated", "message": "会话已过期或无效。"},
        )
    user = (
        await session.execute(
            select(User)
            .options(selectinload(User.student), selectinload(User.teacher))
            .where(User.id == data.user_id)
        )
    ).scalar_one_or_none()
    if user is None:
        await store.delete(token)  # 孤儿会话：清理掉
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthenticated", "message": "用户不存在。"},
        )
    return user


async def get_current_user_id(
    store: SessionStore = Depends(get_session_store),
    token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> int:
    """轻量鉴权：仅校验会话、返回 user_id（不持有 DB 连接），供长连接 SSE 使用。"""
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthenticated", "message": "未登录。"},
        )
    data = await store.get(token)
    if data is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthenticated", "message": "会话已过期或无效。"},
        )
    return data.user_id


async def require_password_changed(user: User = Depends(get_current_user)) -> User:
    """首登强制改密：``must_change_password`` 为真则 403。"""
    if user.must_change_password:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "must_change_password",
                "message": "首次登录需先修改口令。",
            },
        )
    return user


def require_role(*roles: UserRole):
    """角色守卫；链式复用改密校验，角色不符则 403。"""

    async def _dep(user: User = Depends(require_password_changed)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "forbidden",
                    "required": [r.value for r in roles],
                },
            )
        return user

    return _dep
