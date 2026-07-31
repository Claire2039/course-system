"""管理员批量导入用户的请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel

from app.models.constants import UserRole
from app.schemas._types import Email


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
