"""教师工作台路由：我教的教学班、花名册。布置/批改作业复用 M6 的 assignments 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_session, require_role
from app.models import Enrollment, Section, Student, User
from app.models.constants import EnrollmentStatus, UserRole
from app.schemas.catalog import CourseRef
from app.schemas.teacher import MySectionOut, RosterStudentOut

router = APIRouter()


@router.get("/me/sections", response_model=list[MySectionOut])
async def my_sections(
    user: User = Depends(require_role(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
) -> list[MySectionOut]:
    sections = (
        await session.execute(
            select(Section)
            .options(selectinload(Section.course))
            .where(Section.teacher_id == user.id)
            .order_by(Section.id)
        )
    ).scalars().all()
    counts = (
        await session.execute(
            select(Enrollment.section_id, func.count())
            .where(
                Enrollment.status == EnrollmentStatus.ENROLLED,
                Enrollment.section_id.in_([s.id for s in sections]),
            )
            .group_by(Enrollment.section_id)
        )
    ).all()
    count_map = {sid: int(cnt) for sid, cnt in counts}
    return [
        MySectionOut(
            id=s.id,
            course=CourseRef.model_validate(s.course),
            semester_id=s.semester_id,
            capacity=s.capacity,
            seats_taken=s.seats_taken,
            enrolled_count=count_map.get(s.id, 0),
        )
        for s in sections
    ]


@router.get("/sections/{section_id}/roster", response_model=list[RosterStudentOut])
async def roster(
    section_id: int,
    user: User = Depends(require_role(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
) -> list[RosterStudentOut]:
    section = await session.get(Section, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    if section.teacher_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "不是你的教学班。"})
    rows = (
        await session.execute(
            select(Student)
            .options(selectinload(Student.user))
            .join(Enrollment, Enrollment.student_id == Student.user_id)
            .where(
                Enrollment.section_id == section_id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
            )
            .order_by(Student.student_no)
        )
    ).scalars().all()
    return [
        RosterStudentOut(user_id=s.user_id, name=s.user.name, student_no=s.student_no)
        for s in rows
    ]
