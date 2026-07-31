"""作业 / 提交 / 成绩 路由。

教师（require_role(TEACHER) + 拥有该教学班）：布置作业、查花名册、批改。
学生（require_role(STUDENT) + 已选课）：我的作业、提交（multipart→对象存储）、下载附件。
SPEC §4.5 / §5。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_session, get_storage, require_role
from app.core.redis import get_redis
from app.models import Assignment, Enrollment, Grade, Section, Student, Submission, User
from app.models.constants import EnrollmentStatus, UserRole
from app.schemas.assignment import (
    AssignmentOut,
    CreateAssignmentRequest,
    GradeOut,
    GradeRequest,
    MyAssignmentOut,
    RosterSubmissionOut,
    SubmissionOut,
)
from app.services import assignment_service
from app.services.assignment_service import AssignmentError
from app.services.notification import notify, publish_event
from app.services.storage import StorageClient

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _to_http(exc: AssignmentError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
    )


# ---------- 教师 ----------
@router.post("/sections/{section_id}/assignments", response_model=AssignmentOut)
async def create_assignment(
    section_id: int,
    body: CreateAssignmentRequest,
    user: User = Depends(require_role(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
) -> AssignmentOut:
    await assignment_service.assert_teacher_owns(session, user.id, section_id)
    a = Assignment(
        section_id=section_id,
        title=body.title,
        description=body.description,
        due_at=body.due_at,
        late_deadline=body.late_deadline,
        allow_late=body.allow_late,
    )
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return AssignmentOut.model_validate(a)


@router.get(
    "/sections/{section_id}/assignments", response_model=list[AssignmentOut]
)
async def list_section_assignments(
    section_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AssignmentOut]:
    section = await session.get(Section, section_id)
    if section is None:
        raise _to_http(AssignmentError(404, "section_not_found", "教学班不存在。"))
    if section.teacher_id != user.id:
        await assignment_service.assert_student_enrolled(session, user.id, section_id)
    rows = (
        await session.execute(
            select(Assignment)
            .where(Assignment.section_id == section_id)
            .order_by(Assignment.due_at)
        )
    ).scalars().all()
    return [AssignmentOut.model_validate(a) for a in rows]


@router.get(
    "/sections/{section_id}/submissions", response_model=list[RosterSubmissionOut]
)
async def list_section_submissions(
    section_id: int,
    assignment_id: int = Query(...),
    user: User = Depends(require_role(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
) -> list[RosterSubmissionOut]:
    await assignment_service.assert_teacher_owns(session, user.id, section_id)
    students = (
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
    student_ids = [s.user_id for s in students]
    subs = (
        await session.execute(
            select(Submission)
            .options(selectinload(Submission.grade))
            .where(
                Submission.assignment_id == assignment_id,
                Submission.student_id.in_(student_ids),
            )
        )
    ).scalars().all()
    sub_by_student = {s.student_id: s for s in subs}

    out: list[RosterSubmissionOut] = []
    for st in students:
        sub = sub_by_student.get(st.user_id)
        out.append(
            RosterSubmissionOut(
                student_id=st.user_id,
                student_name=st.user.name,
                student_no=st.student_no,
                submission=assignment_service.submission_to_out(sub) if sub else None,
                grade=GradeOut.model_validate(sub.grade) if sub and sub.grade else None,
            )
        )
    return out


@router.post("/submissions/{submission_id}/grade", response_model=GradeOut)
async def grade_submission(
    submission_id: int,
    body: GradeRequest,
    user: User = Depends(require_role(UserRole.TEACHER)),
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> GradeOut:
    try:
        sub = await session.get(Submission, submission_id)
        if sub is None:
            raise AssignmentError(404, "submission_not_found", "提交不存在。")
        assignment = await session.get(Assignment, sub.assignment_id)
        await assignment_service.assert_teacher_owns(session, user.id, assignment.section_id)

        grade = (
            await session.execute(select(Grade).where(Grade.submission_id == submission_id))
        ).scalar_one_or_none()
        if grade is None:
            grade = Grade(
                submission_id=submission_id,
                score=body.score,
                feedback=body.feedback,
                graded_by=user.id,
            )
            session.add(grade)
        else:
            grade.score = body.score
            grade.feedback = body.feedback
            grade.graded_by = user.id

        await notify(
            session,
            sub.student_id,
            "graded",
            {"assignment_id": sub.assignment_id, "score": float(body.score)},
        )
        await session.commit()
        await session.refresh(grade)
        await publish_event(
            redis,
            sub.student_id,
            "graded",
            {"assignment_id": sub.assignment_id, "score": float(body.score)},
        )
        return GradeOut.model_validate(grade)
    except AssignmentError as exc:
        raise _to_http(exc) from exc


# ---------- 学生 ----------
@router.get("/me/assignments", response_model=list[MyAssignmentOut])
async def my_assignments(
    user: User = Depends(require_role(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session),
) -> list[MyAssignmentOut]:
    items = await assignment_service.build_my_assignments(session, user.id)
    return [
        MyAssignmentOut(
            assignment=AssignmentOut.model_validate(ma.assignment),
            submission=assignment_service.submission_to_out(ma.submission)
            if ma.submission
            else None,
            grade=GradeOut.model_validate(ma.grade) if ma.grade else None,
        )
        for ma in items
    ]


@router.post("/assignments/{assignment_id}/submit", response_model=SubmissionOut)
async def submit_assignment(
    assignment_id: int,
    file: UploadFile | None = File(None),
    text_comment: str = Form(default=""),
    user: User = Depends(require_role(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session),
    storage: StorageClient = Depends(get_storage),
) -> SubmissionOut:
    try:
        assignment = await session.get(Assignment, assignment_id)
        if assignment is None:
            raise AssignmentError(404, "assignment_not_found", "作业不存在。")
        await assignment_service.assert_student_enrolled(
            session, user.id, assignment.section_id
        )
        status = assignment_service.compute_submit_status(
            assignment_service.now_utc(),
            assignment.due_at,
            assignment.late_deadline,
            assignment.allow_late,
        )

        file_key: str | None = None
        if file is not None:
            data = await file.read()
            if len(data) > MAX_UPLOAD_BYTES:
                raise AssignmentError(413, "too_large", "文件过大（>10MB）。")
            file_key = f"submissions/{uuid.uuid4().hex}"
            await storage.put(
                file_key, data, file.content_type or "application/octet-stream"
            )

        sub = (
            await session.execute(
                select(Submission).where(
                    Submission.assignment_id == assignment_id,
                    Submission.student_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if sub is None:
            sub = Submission(
                assignment_id=assignment_id,
                student_id=user.id,
                file_key=file_key,
                text_comment=text_comment or None,
                status=status,
            )
            session.add(sub)
        else:
            sub.status = status
            sub.text_comment = text_comment or None
            if file_key is not None:
                sub.file_key = file_key  # 重交：换新文件（无新文件则保留旧文件）
        await session.commit()
        await session.refresh(sub)
        return assignment_service.submission_to_out(sub)
    except AssignmentError as exc:
        # 清理刚上传但写库失败的对象
        raise _to_http(exc) from exc


@router.get("/submissions/{submission_id}/file")
async def download_submission_file(
    submission_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: StorageClient = Depends(get_storage),
) -> Response:
    sub = await session.get(Submission, submission_id)
    if sub is None:
        raise _to_http(AssignmentError(404, "submission_not_found", "提交不存在。"))
    if sub.student_id != user.id:
        assignment = await session.get(Assignment, sub.assignment_id)
        try:
            await assignment_service.assert_teacher_owns(
                session, user.id, assignment.section_id
            )
        except AssignmentError as exc:
            raise _to_http(exc) from exc
    if not sub.file_key:
        raise _to_http(AssignmentError(404, "no_file", "该提交无附件。"))
    data = await storage.get(sub.file_key)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="submission_{submission_id}"'},
    )
