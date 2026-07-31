"""作业 / 提交 / 成绩 的响应与请求模型。

``SubmissionOut`` 不含 ``file_key``（存储内部标识），用 ``has_file`` 暴露是否存在附件；
下载走单独的鉴权端点。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.constants import SubmissionStatus


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    section_id: int
    title: str
    description: str | None = None
    due_at: datetime
    late_deadline: datetime | None = None
    allow_late: bool


class GradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float
    feedback: str | None = None
    graded_at: datetime


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    status: SubmissionStatus
    submitted_at: datetime
    has_file: bool = False
    text_comment: str | None = None


class MyAssignmentOut(BaseModel):
    """学生"我的作业"视角：作业 + 我的提交 + 成绩。"""

    assignment: AssignmentOut
    submission: SubmissionOut | None = None
    grade: GradeOut | None = None


class RosterSubmissionOut(BaseModel):
    """教师花名册视图：学生 + 提交 + 成绩。"""

    student_id: int
    student_name: str
    student_no: str
    submission: SubmissionOut | None = None
    grade: GradeOut | None = None


class CreateAssignmentRequest(BaseModel):
    title: str
    description: str | None = None
    due_at: datetime
    late_deadline: datetime | None = None
    allow_late: bool = False


class GradeRequest(BaseModel):
    score: float
    feedback: str | None = None
