"""CSV 批量导入用户：解析 → 校验 → 查重 → 构建（原子导入的纯逻辑核心）。

尽量把无副作用的逻辑做成纯函数，便于不依赖 TestClient/DB 直接单测。
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_initial_password, hash_password, validate_email_format
from app.models import Student, Teacher, User
from app.models.constants import UserRole

EXPECTED_HEADER = {"role", "name", "email"}

ROLE_REQUIRED: dict[UserRole, set[str]] = {
    UserRole.STUDENT: {"role", "name", "email", "student_no", "grade", "major"},
    UserRole.TEACHER: {"role", "name", "email", "teacher_no", "department", "title"},
    UserRole.ADMIN: {"role", "name", "email"},
}


@dataclass
class ValidatedUser:
    row: int  # 原始 CSV 数据行号（1-based）
    role: UserRole
    name: str
    email: str
    student_no: str | None = None
    grade: int | None = None
    major: str | None = None
    teacher_no: str | None = None
    department: str | None = None
    title: str | None = None
    initial_password: str = ""


@dataclass
class RowError:
    row: int
    code: str
    message: str


@dataclass
class ExistingKeys:
    emails: set[str] = field(default_factory=set)
    student_nos: set[str] = field(default_factory=set)
    teacher_nos: set[str] = field(default_factory=set)


def parse_csv(raw: str) -> list[dict[str, str]]:
    """解析 CSV 为行字典列表；表头缺少必要列时抛 ``ValueError("invalid_header")``。"""
    reader = csv.DictReader(io.StringIO(raw))
    fields = reader.fieldnames or []
    stripped_fields = {f.strip() for f in fields if f}
    if not EXPECTED_HEADER.issubset(stripped_fields):
        raise ValueError("invalid_header")

    rows: list[dict[str, str]] = []
    for raw_row in reader:
        clean: dict[str, str] = {}
        for k, v in raw_row.items():
            if k is None:
                continue  # 多余列落到 None 键，忽略
            clean[k.strip()] = v.strip() if isinstance(v, str) else ""
        rows.append(clean)
    return rows


def validate_rows(rows: list[dict[str, str]]) -> tuple[list[ValidatedUser], list[RowError]]:
    """纯校验：角色/必填/邮箱格式/批内去重。返回 (合法用户, 错误列表)。"""
    users: list[ValidatedUser] = []
    errors: list[RowError] = []
    seen_emails: set[str] = set()
    seen_student_no: set[str] = set()
    seen_teacher_no: set[str] = set()

    for idx, r in enumerate(rows, start=1):
        role_str = (r.get("role") or "").strip().upper()
        try:
            role = UserRole(role_str)
        except ValueError:
            errors.append(RowError(idx, "invalid_role", f"未知角色: {role_str!r}"))
            continue

        required = ROLE_REQUIRED[role]
        missing = [f for f in required if not (r.get(f) or "").strip()]
        if missing:
            errors.append(
                RowError(idx, "missing_field", f"缺少必填字段: {', '.join(missing)}")
            )
            continue

        email = r["email"].strip()
        try:
            validate_email_format(email)
        except ValueError:
            errors.append(RowError(idx, "invalid_email", f"邮箱格式非法: {email!r}"))
            continue

        if email in seen_emails:
            errors.append(RowError(idx, "duplicate_email", f"文件内重复邮箱: {email}"))
            continue
        seen_emails.add(email)

        vu = ValidatedUser(
            row=idx,
            role=role,
            name=r["name"].strip(),
            email=email,
            initial_password=generate_initial_password(),
        )

        if role is UserRole.STUDENT:
            sno = r["student_no"].strip()
            if sno in seen_student_no:
                errors.append(RowError(idx, "duplicate_student_no", f"文件内重复学号: {sno}"))
                continue
            seen_student_no.add(sno)
            try:
                grade = int(r["grade"])
            except (TypeError, ValueError):
                errors.append(RowError(idx, "invalid_grade", f"grade 必须是整数: {r.get('grade')!r}"))
                continue
            vu.student_no = sno
            vu.grade = grade
            vu.major = r["major"].strip()
        elif role is UserRole.TEACHER:
            tno = r["teacher_no"].strip()
            if tno in seen_teacher_no:
                errors.append(RowError(idx, "duplicate_teacher_no", f"文件内重复工号: {tno}"))
                continue
            seen_teacher_no.add(tno)
            vu.teacher_no = tno
            vu.department = r["department"].strip()
            vu.title = r["title"].strip()

        users.append(vu)

    return users, errors


async def fetch_existing_keys(
    session: AsyncSession,
    emails: set[str],
    student_nos: set[str],
    teacher_nos: set[str],
) -> ExistingKeys:
    """一次性查出已存在的自然键，供查重。"""
    res = ExistingKeys()
    if emails:
        res.emails = set(
            (await session.execute(select(User.email).where(User.email.in_(emails)))).scalars().all()
        )
    if student_nos:
        res.student_nos = set(
            (await session.execute(
                select(Student.student_no).where(Student.student_no.in_(student_nos))
            )).scalars().all()
        )
    if teacher_nos:
        res.teacher_nos = set(
            (await session.execute(
                select(Teacher.teacher_no).where(Teacher.teacher_no.in_(teacher_nos))
            )).scalars().all()
        )
    return res


def build_users(validated: list[ValidatedUser]) -> list[User]:
    """把已校验行构造成 ORM 对象（含初始口令哈希、must_change_password=True）。"""
    users: list[User] = []
    for v in validated:
        pw_hash = hash_password(v.initial_password)
        common = dict(
            email=v.email,
            password_hash=pw_hash,
            role=v.role,
            name=v.name,
            must_change_password=True,
        )
        if v.role is UserRole.STUDENT:
            users.append(
                User(
                    **common,
                    student=Student(
                        student_no=v.student_no, grade=v.grade, major=v.major
                    ),
                )
            )
        elif v.role is UserRole.TEACHER:
            users.append(
                User(
                    **common,
                    teacher=Teacher(
                        teacher_no=v.teacher_no, department=v.department, title=v.title
                    ),
                )
            )
        else:  # ADMIN：无 Student/Teacher 附属行
            users.append(User(**common))
    return users
