"""管理员路由：批量导入用户 + 课程/教学班/学期 CRUD + 教师列表。

全部需要 ADMIN（路由器级依赖）。删除被引用的对象返回 409（不级联）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_session, require_role
from app.models import Course, Enrollment, Section, Semester, Teacher, User
from app.models.constants import EnrollmentStatus, UserRole
from app.schemas.admin import (
    AdminSectionOut,
    AdminSemesterOut,
    AdminTeacherOut,
    CourseCreate,
    CourseUpdate,
    ImportUsersErrorResponse,
    ImportedUserRow,
    ImportUsersResponse,
    SectionCreate,
    SectionUpdate,
    SemesterCreate,
    SemesterUpdate,
)
from app.schemas.catalog import CourseOut
from app.services import user_import

router = APIRouter(dependencies=[Depends(require_role(UserRole.ADMIN))])


# ---------- 批量导入用户 ----------
@router.post("/import-users", response_model=ImportUsersResponse)
async def import_users(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> ImportUsersResponse:
    raw = (await file.read()).decode("utf-8", errors="replace")
    try:
        rows = user_import.parse_csv(raw)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_header", "message": "CSV 表头至少需包含: role,name,email"},
        )

    validated, errors = user_import.validate_rows(rows)
    if not validated and not errors:
        raise HTTPException(
            status_code=400, detail={"code": "empty", "message": "未发现用户数据行。"}
        )

    existing = await user_import.fetch_existing_keys(
        session,
        emails={v.email for v in validated},
        student_nos={v.student_no for v in validated if v.student_no},
        teacher_nos={v.teacher_no for v in validated if v.teacher_no},
    )
    for v in validated:
        if v.email in existing.emails:
            errors.append(user_import.RowError(v.row, "duplicate_email", f"邮箱已存在: {v.email}"))
        if v.role is UserRole.STUDENT and v.student_no in existing.student_nos:
            errors.append(
                user_import.RowError(v.row, "duplicate_student_no", f"学号已存在: {v.student_no}")
            )
        if v.role is UserRole.TEACHER and v.teacher_no in existing.teacher_nos:
            errors.append(
                user_import.RowError(v.row, "duplicate_teacher_no", f"工号已存在: {v.teacher_no}")
            )

    if errors:
        raise HTTPException(
            status_code=422,
            detail=ImportUsersErrorResponse(errors=errors).model_dump(),
        )

    users = user_import.build_users(validated)
    session.add_all(users)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "并发冲突，请重试。"},
        )

    rows_out = [
        ImportedUserRow(
            email=u.email,
            name=u.name,
            role=u.role,
            student_no=u.student.student_no if u.student else None,
            grade=u.student.grade if u.student else None,
            major=u.student.major if u.student else None,
            teacher_no=u.teacher.teacher_no if u.teacher else None,
            department=u.teacher.department if u.teacher else None,
            title=u.teacher.title if u.teacher else None,
            initial_password=v.initial_password,
        )
        for u, v in zip(users, validated)
    ]
    return ImportUsersResponse(imported=len(users), users=rows_out)


# ---------- 教师（供分班下拉） ----------
@router.get("/teachers", response_model=list[AdminTeacherOut])
async def list_teachers(session: AsyncSession = Depends(get_session)) -> list[AdminTeacherOut]:
    rows = (
        await session.execute(
            select(Teacher)
            .options(selectinload(Teacher.user))
            .order_by(Teacher.teacher_no)
        )
    ).scalars().all()
    return [
        AdminTeacherOut(
            id=t.user_id, name=t.user.name, teacher_no=t.teacher_no, department=t.department
        )
        for t in rows
    ]


# ---------- 课程 CRUD ----------
@router.post("/courses", response_model=CourseOut)
async def create_course(
    body: CourseCreate, session: AsyncSession = Depends(get_session)
) -> CourseOut:
    c = Course(**body.model_dump())
    session.add(c)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail={"code": "conflict", "message": "课程代码已存在。"})
    await session.refresh(c)
    return CourseOut.model_validate(c)


@router.patch("/courses/{course_id}", response_model=CourseOut)
async def update_course(
    course_id: int, body: CourseUpdate, session: AsyncSession = Depends(get_session)
) -> CourseOut:
    c = await session.get(Course, course_id)
    if c is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    await session.commit()
    await session.refresh(c)
    return CourseOut.model_validate(c)


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(course_id: int, session: AsyncSession = Depends(get_session)) -> None:
    ref = (
        await session.execute(
            select(func.count()).select_from(Section).where(Section.course_id == course_id)
        )
    ).scalar_one()
    if ref > 0:
        raise HTTPException(
            status_code=409, detail={"code": "in_use", "message": "该课程仍有教学班，无法删除。"}
        )
    c = await session.get(Course, course_id)
    if c is not None:
        await session.delete(c)
        await session.commit()


# ---------- 教学班 CRUD ----------
@router.post("/sections", response_model=AdminSectionOut)
async def create_section(
    body: SectionCreate, session: AsyncSession = Depends(get_session)
) -> AdminSectionOut:
    s = Section(**body.model_dump())
    session.add(s)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail={"code": "conflict", "message": "引用的课程/教师/学期不存在。"}
        )
    await session.refresh(s)
    return AdminSectionOut.model_validate(s)


@router.patch("/sections/{section_id}", response_model=AdminSectionOut)
async def update_section(
    section_id: int, body: SectionUpdate, session: AsyncSession = Depends(get_session)
) -> AdminSectionOut:
    s = await session.get(Section, section_id)
    if s is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail={"code": "conflict", "message": "引用的课程/教师/学期不存在。"}
        )
    await session.refresh(s)
    return AdminSectionOut.model_validate(s)


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(section_id: int, session: AsyncSession = Depends(get_session)) -> None:
    ref = (
        await session.execute(
            select(func.count())
            .select_from(Enrollment)
            .where(Enrollment.section_id == section_id)
        )
    ).scalar_one()
    if ref > 0:
        raise HTTPException(
            status_code=409, detail={"code": "in_use", "message": "该教学班仍有学生选课，无法删除。"}
        )
    s = await session.get(Section, section_id)
    if s is not None:
        await session.delete(s)
        await session.commit()


# ---------- 学期 CRUD ----------
async def _set_single_current(session: AsyncSession, semester_id: int) -> None:
    """保证同一时刻只有一个 is_current 学期。"""
    rows = (
        await session.execute(
            select(Semester).where(Semester.is_current.is_(True), Semester.id != semester_id)
        )
    ).scalars().all()
    for r in rows:
        r.is_current = False


@router.get("/semesters", response_model=list[AdminSemesterOut])
async def list_semesters(session: AsyncSession = Depends(get_session)) -> list[AdminSemesterOut]:
    rows = (
        await session.execute(select(Semester).order_by(Semester.id.desc()))
    ).scalars().all()
    return [AdminSemesterOut.model_validate(r) for r in rows]


@router.post("/semesters", response_model=AdminSemesterOut)
async def create_semester(
    body: SemesterCreate, session: AsyncSession = Depends(get_session)
) -> AdminSemesterOut:
    sem = Semester(**body.model_dump())
    session.add(sem)
    await session.flush()
    if sem.is_current:
        await _set_single_current(session, sem.id)
    await session.commit()
    await session.refresh(sem)
    return AdminSemesterOut.model_validate(sem)


@router.patch("/semesters/{semester_id}", response_model=AdminSemesterOut)
async def update_semester(
    semester_id: int, body: SemesterUpdate, session: AsyncSession = Depends(get_session)
) -> AdminSemesterOut:
    sem = await session.get(Semester, semester_id)
    if sem is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(sem, k, v)
    if sem.is_current:
        await _set_single_current(session, sem.id)
    await session.commit()
    await session.refresh(sem)
    return AdminSemesterOut.model_validate(sem)
