"""认证全流程集成测试：需 TEST_DATABASE_URL；Redis 走 fakeredis。

覆盖：login → /me → 错误口令 → change-password → 政策校验 → logout → 登出后 401、
must_change 阻断受保护端点、改密后 DB 状态刷新。
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.main import app
from app.models import Student, User
from app.models.constants import UserRole

pytestmark = pytest.mark.integration

PWD = "OldPass#2026"


async def _seed(db, email: str, role: UserRole, must_change: bool, **profile) -> None:
    async with db() as s:
        s.add(
            User(
                email=email,
                password_hash=hash_password(PWD),
                role=role,
                name=email.split("@")[0],
                must_change_password=must_change,
                **profile,
            )
        )
        await s.commit()


async def test_full_login_me_change_logout(auth_db) -> None:
    await _seed(
        auth_db,
        "stu@seed.example.com",
        UserRole.STUDENT,
        must_change=True,
        student=Student(student_no="S1", grade=2024, major="CS"),
    )

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/api/v1/auth/login", json={"email": "stu@seed.example.com", "password": PWD})
        assert r.status_code == 200, r.text
        assert r.json()["user"]["must_change_password"] is True

        r = await ac.get("/api/v1/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "stu@seed.example.com"
        assert body["student"]["student_no"] == "S1"

        r = await ac.post("/api/v1/auth/login", json={"email": "stu@seed.example.com", "password": "wrong"})
        assert r.status_code == 401

        r = await ac.post(
            "/api/v1/auth/change-password",
            json={"old_password": PWD, "new_password": "BrandNew#1"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["user"]["must_change_password"] is False

        r = await ac.post(
            "/api/v1/auth/change-password",
            json={"old_password": "BrandNew#1", "new_password": "short"},
        )
        assert r.status_code == 400

        r = await ac.post(
            "/api/v1/auth/change-password",
            json={"old_password": "nope", "new_password": "Another#1"},
        )
        assert r.status_code == 401

        r = await ac.post("/api/v1/auth/logout")
        assert r.status_code == 200

        r = await ac.get("/api/v1/auth/me")
        assert r.status_code == 401


async def test_must_change_blocks_guarded_endpoint(auth_db) -> None:
    await _seed(
        auth_db,
        "stu@seed.example.com",
        UserRole.STUDENT,
        must_change=True,
        student=Student(student_no="S1", grade=2024, major="CS"),
    )
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await ac.post("/api/v1/auth/login", json={"email": "stu@seed.example.com", "password": PWD})
        # require_role(ADMIN) 先经 require_password_changed → must_change 优先 → 403
        r = await ac.post(
            "/api/v1/admin/import-users",
            files={"file": ("u.csv", b"role,name,email\n", "text/csv")},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "must_change_password"


async def test_db_reflects_password_change(auth_db) -> None:
    await _seed(
        auth_db,
        "stu@seed.example.com",
        UserRole.STUDENT,
        must_change=True,
        student=Student(student_no="S1", grade=2024, major="CS"),
    )
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await ac.post("/api/v1/auth/login", json={"email": "stu@seed.example.com", "password": PWD})
        await ac.post(
            "/api/v1/auth/change-password",
            json={"old_password": PWD, "new_password": "BrandNew#1"},
        )

    async with auth_db() as s:
        u = (await s.execute(select(User).where(User.email == "stu@seed.example.com"))).scalar_one()
        assert u.must_change_password is False

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/api/v1/auth/login", json={"email": "stu@seed.example.com", "password": "BrandNew#1"})
        assert r.status_code == 200
