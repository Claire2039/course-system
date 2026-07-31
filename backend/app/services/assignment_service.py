"""作业业务逻辑：权限校验、提交状态计算、"我的作业"组装。

教师"拥有"教学班的判定：``section.teacher_id == user.id``（teachers.user_id 即 user.id），
无需懒加载关系。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Assignment, Enrollment, Grade, Section, Submission
from app.models.constants import EnrollmentStatus, SubmissionStatus
from app.schemas.assignment import SubmissionOut


class AssignmentError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def compute_submit_status(
    now: datetime,
    due_at: datetime,
    late_deadline: datetime | None,
    allow_late: bool,
) -> SubmissionStatus:
    """按时间判定提交状态；过硬截止抛 ``AssignmentError(409, deadline_passed)``。"""
    if now <= due_at:
        return SubmissionStatus.SUBMITTED
    if allow_late and late_deadline is not None and now <= late_deadline:
        return SubmissionStatus.LATE
    raise AssignmentError(409, "deadline_passed", "作业已过截止时间，无法提交。")


async def assert_teacher_owns(
    session: AsyncSession, user_id: int, section_id: int
) -> Section:
    section = await session.get(Section, section_id)
    if section is None:
        raise AssignmentError(404, "section_not_found", "教学班不存在。")
    if section.teacher_id != user_id:
        raise AssignmentError(403, "forbidden", "你不是该教学班的授课教师。")
    return section


async def assert_student_enrolled(
    session: AsyncSession, user_id: int, section_id: int
) -> None:
    row = (
        await session.execute(
            select(Enrollment.id).where(
                Enrollment.section_id == section_id,
                Enrollment.student_id == user_id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
            )
        )
    ).first()
    if row is None:
        raise AssignmentError(403, "forbidden", "你未选该教学班。")


def submission_to_out(s: Submission) -> SubmissionOut:
    """构造 SubmissionOut（has_file 由 file_key 是否存在派生）。"""
    return SubmissionOut(
        id=s.id,
        assignment_id=s.assignment_id,
        status=s.status,
        submitted_at=s.submitted_at,
        has_file=bool(s.file_key),
        text_comment=s.text_comment,
    )


@dataclass
class MyAssignment:
    assignment: Assignment
    submission: Submission | None
    grade: Grade | None


async def build_my_assignments(
    session: AsyncSession, student_id: int
) -> list[MyAssignment]:
    """该生所有已选教学班的作业 + 其提交（含成绩）。"""
    assignments = (
        await session.execute(
            select(Assignment)
            .join(Section, Assignment.section_id == Section.id)
            .join(Enrollment, Enrollment.section_id == Section.id)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
            )
            .order_by(Assignment.due_at)
        )
    ).scalars().all()
    if not assignments:
        return []

    assignment_ids = [a.id for a in assignments]
    submissions = (
        await session.execute(
            select(Submission)
            .options(selectinload(Submission.grade))
            .where(
                Submission.assignment_id.in_(assignment_ids),
                Submission.student_id == student_id,
            )
        )
    ).scalars().all()
    sub_map = {s.assignment_id: s for s in submissions}

    return [
        MyAssignment(a, sub_map.get(a.id), (sub_map[a.id].grade if a.id in sub_map else None))
        for a in assignments
    ]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
