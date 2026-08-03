"""选课 / 退课 / 我的选课 / 我的候补 路由（学生）。

SPEC §5 Enrollment：``POST /sections/{id}/enroll`` · ``DELETE /enrollments/{id}`` ·
``GET /me/enrollments`` · ``GET /me/waitlist``。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_role
from app.core.redis import get_redis
from app.db.session import get_session
from app.models import Enrollment, Section, User
from app.models.constants import EnrollmentStatus, UserRole
from app.schemas.enrollment import EnrollmentOut, EnrollResponse
from app.services import enrollment_service

router = APIRouter()


def _to_http(exc: enrollment_service.EnrollmentError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
    )


@router.post("/sections/{section_id}/enroll", response_model=EnrollResponse)
async def enroll(
    section_id: int,
    request: Request,
    user: User = Depends(require_role(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session),
) -> EnrollResponse:
    try:
        result = await enrollment_service.enroll(
            session, get_redis(request), user.id, section_id
        )
    except enrollment_service.EnrollmentError as exc:
        raise _to_http(exc) from exc
    return EnrollResponse(
        status=result.status, enrollment_id=result.enrollment_id, position=result.position
    )


@router.delete("/enrollments/{enrollment_id}")
async def drop_enrollment(
    enrollment_id: int,
    request: Request,
    user: User = Depends(require_role(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        await enrollment_service.drop(
            session, get_redis(request), user.id, enrollment_id
        )
    except enrollment_service.EnrollmentError as exc:
        raise _to_http(exc) from exc
    return {"ok": True}


@router.get("/me/enrollments", response_model=list[EnrollmentOut])
async def my_enrollments(
    user: User = Depends(require_role(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session),
) -> list[EnrollmentOut]:
    rows = (
        await session.execute(
            select(Enrollment)
            .options(
                selectinload(Enrollment.section).selectinload(Section.course),
                selectinload(Enrollment.section).selectinload(Section.time_slots),
            )
            .where(
                Enrollment.student_id == user.id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
            )
            .order_by(Enrollment.id)
        )
    ).scalars().all()
    return [EnrollmentOut.model_validate(e) for e in rows]


@router.get("/me/waitlist", response_model=list[EnrollmentOut])
async def my_waitlist(
    user: User = Depends(require_role(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session),
) -> list[EnrollmentOut]:
    rows = (
        await session.execute(
            select(Enrollment)
            .options(
                selectinload(Enrollment.section).selectinload(Section.course),
                selectinload(Enrollment.section).selectinload(Section.time_slots),
            )
            .where(
                Enrollment.student_id == user.id,
                Enrollment.status == EnrollmentStatus.WAITLISTED,
            )
            .order_by(Enrollment.waitlist_position, Enrollment.id)
        )
    ).scalars().all()
    return [EnrollmentOut.model_validate(e) for e in rows]
