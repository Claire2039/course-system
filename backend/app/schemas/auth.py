"""认证相关的 Pydantic v2 模型。

``UserMe`` 不含 ``password_hash``——该字段根本不声明，``from_attributes`` 只会拉取已声明字段，
因此口令哈希不可能从响应里泄露。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.constants import UserRole
from app.schemas._types import Email


class LoginRequest(BaseModel):
    email: Email
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class StudentProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_no: str
    grade: int
    major: str


class TeacherProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    teacher_no: str
    department: str
    title: str


class UserMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: Email
    name: str
    role: UserRole
    must_change_password: bool
    student: StudentProfile | None = None
    teacher: TeacherProfile | None = None


class LoginResponse(BaseModel):
    user: UserMe


class ChangePasswordResponse(BaseModel):
    user: UserMe


class LogoutResponse(BaseModel):
    ok: bool = True
