"""目录浏览路由：courses / sections / teachers / periods。

全体已登录用户可浏览（``get_current_user``，不限角色；不强制改密校验，避免 must_change
用户被困）。路由器级依赖统一加鉴权。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Course, CoursePrerequisite, PeriodDef, Section, Semester, Teacher
from app.schemas.catalog import (
    CourseDetail,
    CourseOut,
    CourseRef,
    Page,
    PeriodDefOut,
    PrereqRef,
    SectionOut,
    TeacherDetail,
    TeacherOut,
    TeacherRef,
    TimeSlotOut,
)

router = APIRouter(dependencies=[Depends(get_current_user)])

DEFAULT_LIMIT = 50
MAX_LIMIT = 100

_SECTION_OPTIONS = (
    selectinload(Section.course),
    selectinload(Section.teacher).selectinload(Teacher.user),
    selectinload(Section.time_slots),
)


def _section_out(s: Section) -> SectionOut:
    return SectionOut(
        id=s.id,
        capacity=s.capacity,
        seats_taken=s.seats_taken,
        room=s.room,
        semester_id=s.semester_id,
        course=CourseRef.model_validate(s.course),
        teacher=TeacherRef(name=s.teacher.user.name, teacher_no=s.teacher.teacher_no, bio=s.teacher.bio),
        time_slots=[TimeSlotOut.model_validate(t) for t in s.time_slots],
    )


async def _current_semester_id(session: AsyncSession) -> int | None:
    res = await session.execute(
        select(Semester.id).where(Semester.is_current.is_(True)).limit(1)
    )
    return res.scalar_one_or_none()


@router.get("/courses", response_model=Page[CourseOut])
async def list_courses(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> Page[CourseOut]:
    total = (await session.execute(select(func.count(Course.id)))).scalar_one()
    rows = (
        await session.execute(
            select(Course).order_by(Course.code).limit(limit).offset(offset)
        )
    ).scalars().all()
    return Page(
        items=[CourseOut.model_validate(c) for c in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/courses/{course_id}", response_model=CourseDetail)
async def get_course(
    course_id: int, session: AsyncSession = Depends(get_session)
) -> CourseDetail:
    stmt = (
        select(Course)
        .options(
            selectinload(Course.prerequisites).selectinload(
                CoursePrerequisite.prereq_course
            )
        )
        .where(Course.id == course_id)
    )
    c = (await session.execute(stmt)).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return CourseDetail(
        id=c.id,
        code=c.code,
        title=c.title,
        credits=c.credits,
        department=c.department,
        category=c.category,
        cover_url=c.cover_url,
        description=c.description,
        syllabus=c.syllabus or [],
        prerequisites=[
            PrereqRef(code=p.prereq_course.code, title=p.prereq_course.title)
            for p in c.prerequisites
        ],
    )


@router.get("/sections", response_model=Page[SectionOut])
async def list_sections(
    session: AsyncSession = Depends(get_session),
    semester_id: int | None = None,
    course_id: int | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> Page[SectionOut]:
    if semester_id is None:
        semester_id = await _current_semester_id(session)  # 默认当前学期

    stmt = select(Section)
    count_stmt = select(func.count(Section.id))
    if semester_id is not None:
        stmt = stmt.where(Section.semester_id == semester_id)
        count_stmt = count_stmt.where(Section.semester_id == semester_id)
    if course_id is not None:
        stmt = stmt.where(Section.course_id == course_id)
        count_stmt = count_stmt.where(Section.course_id == course_id)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        await session.execute(
            stmt.options(*_SECTION_OPTIONS).order_by(Section.id).limit(limit).offset(offset)
        )
    ).scalars().all()
    return Page(
        items=[_section_out(s) for s in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sections/{section_id}", response_model=SectionOut)
async def get_section(
    section_id: int, session: AsyncSession = Depends(get_session)
) -> SectionOut:
    stmt = (
        select(Section).options(*_SECTION_OPTIONS).where(Section.id == section_id)
    )
    s = (await session.execute(stmt)).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return _section_out(s)


@router.get("/teachers", response_model=Page[TeacherOut])
async def list_teachers(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> Page[TeacherOut]:
    total = (await session.execute(select(func.count(Teacher.user_id)))).scalar_one()
    rows = (
        await session.execute(
            select(Teacher)
            .options(selectinload(Teacher.user))
            .order_by(Teacher.teacher_no)
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return Page(
        items=[
            TeacherOut(
                id=t.user_id,
                name=t.user.name,
                teacher_no=t.teacher_no,
                department=t.department,
                title=t.title,
            )
            for t in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/teachers/{teacher_id}", response_model=TeacherDetail)
async def get_teacher(
    teacher_id: int, session: AsyncSession = Depends(get_session)
) -> TeacherDetail:
    stmt = (
        select(Teacher)
        .options(selectinload(Teacher.user))
        .where(Teacher.user_id == teacher_id)
    )
    t = (await session.execute(stmt)).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return TeacherDetail(
        id=t.user_id,
        name=t.user.name,
        teacher_no=t.teacher_no,
        department=t.department,
        title=t.title,
        bio=t.bio,
        research_interests=t.research_interests,
        education=t.education,
        publications=t.publications,
    )


@router.get("/periods", response_model=list[PeriodDefOut])
async def list_periods(session: AsyncSession = Depends(get_session)) -> list[PeriodDefOut]:
    rows = (
        await session.execute(select(PeriodDef).order_by(PeriodDef.period_no))
    ).scalars().all()
    return [PeriodDefOut.model_validate(p) for p in rows]
