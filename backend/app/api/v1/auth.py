"""认证路由：login / logout / me / change-password。

login/logout/me/change-password 用 ``get_current_user``（不含改密校验）——否则
``must_change_password`` 用户会被困住、无法到达 change-password。
"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session_store
from app.core.config import settings
from app.core.security import hash_password, validate_password_change, verify_password
from app.db.session import get_session
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    UserMe,
)
from app.services.session_store import SessionStore

router = APIRouter()


def _cookie_kwargs() -> dict:
    """会话 Cookie 属性：httpOnly + SameSite=Lax + 生产环境 Secure。"""
    return {
        "key": settings.session_cookie_name,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.environment != "development",
        "domain": settings.session_cookie_domain or None,
        "max_age": settings.session_ttl_seconds,
        "path": "/",
    }


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
    store: SessionStore = Depends(get_session_store),
) -> LoginResponse:
    # 反枚举：邮箱不存在与口令错误返回同一个 401。
    user = (
        await session.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(
        user.password_hash, body.password
    ):
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "邮箱或口令错误。"},
        )
    sid = await store.create(user.id)
    response.set_cookie(value=sid, **_cookie_kwargs())
    return LoginResponse(user=UserMe.model_validate(user))


@router.get("/me", response_model=UserMe)
async def me(user: User = Depends(get_current_user)) -> UserMe:
    return UserMe.model_validate(user)


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    store: SessionStore = Depends(get_session_store),
    token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> ChangePasswordResponse:
    if not verify_password(user.password_hash, body.old_password):
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "旧口令错误。"},
        )
    try:
        validate_password_change(body.new_password, body.old_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": str(exc)})

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    await session.commit()

    # 轮换会话：作废旧 sid、签发新 sid，避免改密前泄露的 cookie 继续有效。
    if token:
        await store.delete(token)
    new_sid = await store.create(user.id)
    response.set_cookie(value=new_sid, **_cookie_kwargs())
    return ChangePasswordResponse(user=UserMe.model_validate(user))


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    user: User = Depends(get_current_user),
    store: SessionStore = Depends(get_session_store),
    token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> LogoutResponse:
    if token:
        await store.delete(token)
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        domain=settings.session_cookie_domain or None,
    )
    return LogoutResponse()
