"""管理员路由：批量导入用户（CSV）。

原子导入：先全部解析校验 + 查重，任一错误则 422 且不写入任何数据；否则单事务提交。
初始随机口令仅此一次随响应返回，供管理员分发。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.session import get_session
from app.models import User
from app.models.constants import UserRole
from app.schemas.admin import (
    ImportedUserRow,
    ImportUsersResponse,
    ImportUsersErrorResponse,
)
from app.services import user_import

router = APIRouter()


@router.post("/import-users", response_model=ImportUsersResponse)
async def import_users(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_role(UserRole.ADMIN)),
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
