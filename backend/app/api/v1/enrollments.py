"""选课 / 退课 / 我的选课 / 我的候补 路由（学生）。

SPEC §5 Enrollment：``POST /sections/{id}/enroll`` · ``DELETE /enrollments/{id}`` ·
``GET /me/enrollments`` · ``GET /me/waitlist``。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_role
from app.core.redis import get_redis
from app.db.session import get_session
from app.models import Enrollment, PeriodDef, Section, User
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


@router.get("/me/schedule.ics")
async def my_schedule_ics(
    user: User = Depends(require_role(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """导出当前学期课表为 iCalendar（.ics），按周重复 16 周。"""
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

    periods = {
        p.period_no: p
        for p in (await session.execute(select(PeriodDef))).scalars().all()
    }

    today = datetime.now().astimezone().date()
    base_monday = today - timedelta(days=today.weekday())  # 本周周一
    weeks = 16
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//选课系统//Schedule Export//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for e in rows:
        sec = e.section
        summary = f"{sec.course.code} {sec.course.title}"
        for ts in sec.time_slots:
            sp = periods.get(ts.start_period)
            ep = periods.get(ts.end_period)
            if not sp or not ep:
                continue
            day = base_monday + timedelta(days=ts.day_of_week - 1)
            dtstart = datetime.combine(day, sp.start_time)
            dtend = datetime.combine(day, ep.end_time)
            lines += [
                "BEGIN:VEVENT",
                f"UID:enr{e.id}-d{ts.day_of_week}-p{ts.start_period}@course-system",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{dtstart.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND:{dtend.strftime('%Y%m%dT%H%M%S')}",
                f"RRULE:FREQ=WEEKLY;COUNT={weeks}",
                f"SUMMARY:{summary}",
                f"LOCATION:{sec.room}",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")

    body = "\r\n".join(lines) + "\r\n"
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="schedule.ics"'},
    )


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
