"""管理员相关模型：批量导入用户 + 课程/教学班/学期 CRUD。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.constants import UserRole
from app.schemas._types import Email


# ---------- 批量导入用户 ----------
class ImportedUserRow(BaseModel):
    email: Email
    name: str
    role: UserRole
    student_no: str | None = None
    grade: int | None = None
    major: str | None = None
    teacher_no: str | None = None
    department: str | None = None
    title: str | None = None
    initial_password: str  # 仅此一次返回，绝不落库


class ImportUsersResponse(BaseModel):
    imported: int
    users: list[ImportedUserRow]


class ImportRowError(BaseModel):
    row: int  # 1-based 数据行号
    code: str
    message: str


class ImportUsersErrorResponse(BaseModel):
    errors: list[ImportRowError]
    imported: int = 0


# ---------- 课程 CRUD ----------
class CourseCreate(BaseModel):
    code: str
    title: str
    credits: int
    description: str | None = None
    department: str


class CourseUpdate(BaseModel):
    code: str | None = None
    title: str | None = None
    credits: int | None = None
    description: str | None = None
    department: str | None = None


# ---------- 教学班 CRUD ----------
class SectionCreate(BaseModel):
    course_id: int
    teacher_id: int
    semester_id: int
    capacity: int
    room: str


class SectionUpdate(BaseModel):
    course_id: int | None = None
    teacher_id: int | None = None
    semester_id: int | None = None
    capacity: int | None = None
    room: str | None = None


class AdminSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    teacher_id: int
    semester_id: int
    capacity: int
    seats_taken: int
    room: str


# ---------- 学期 CRUD ----------
class SemesterCreate(BaseModel):
    name: str
    is_current: bool = False
    enroll_open_at: datetime
    enroll_close_at: datetime
    drop_deadline: datetime
    max_credits: int
    max_courses: int


class SemesterUpdate(BaseModel):
    name: str | None = None
    is_current: bool | None = None
    enroll_open_at: datetime | None = None
    enroll_close_at: datetime | None = None
    drop_deadline: datetime | None = None
    max_credits: int | None = None
    max_courses: int | None = None


class AdminSemesterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_current: bool
    enroll_open_at: datetime
    enroll_close_at: datetime
    drop_deadline: datetime
    max_credits: int
    max_courses: int


# ---------- 教师（供分班下拉） ----------
class AdminTeacherOut(BaseModel):
    id: int  # = user_id
    name: str
    teacher_no: str
    department: str
