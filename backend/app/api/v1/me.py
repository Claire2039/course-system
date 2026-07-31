"""当前用户的通知历史（SPEC §4.4：事件同时落库，刷新后可查）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Notification, User
from app.schemas.notification import NotificationOut

router = APIRouter()


@router.get("/me/notifications", response_model=list[NotificationOut])
async def list_notifications(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=100),
) -> list[NotificationOut]:
    rows = (
        await session.execute(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [NotificationOut.model_validate(n) for n in rows]
