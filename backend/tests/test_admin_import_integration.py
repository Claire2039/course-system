"""管理员 CSV 批量导入集成测试：需 TEST_DATABASE_URL；Redis 走 fakeredis。

覆盖：原子成功导入（返回一次性初始口令、DB 落库）、已存在邮箱导致整批 422（原子性）、
学生角色被拒（forbidden）。
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.main import app
from app.models import Student, User
from app.models.constants import UserRole

pytestmark = pytest.mark.integration

ADMIN_PWD = "Admin#2026"
HDR = "role,name,email,student_no,grade,major,teacher_no,department,title\n"


async def _seed_admin(db, email="admin@seed.example.com") -> None:
    async with db() as s:
        s.add(
            User(
                email=email,
                password_hash=hash_password(ADMIN_PWD),
                role=UserRole.ADMIN,
                name="Admin",
                must_change_password=False,
            )
        )
        await s.commit()


async def test_import_atomic_success(auth_db) -> None:
    await _seed_admin(auth_db)
    csv_bytes = HDR + "STUDENT,S1,s1@seed.example.com,S9001,2024,CS,,,,\nTEACHER,T1,t1@seed.example.com,,,,,T001,CS,Lecturer\n"
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await ac.post("/api/v1/auth/login", json={"email": "admin@seed.example.com", "password": ADMIN_PWD})
        r = await ac.post("/api/v1/admin/import-users", files={"file": ("u.csv", csv_bytes, "text/csv")})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["imported"] == 2
        assert all(u["initial_password"] for u in body["users"])

    async with auth_db() as s:
        emails = set((await s.execute(select(User.email))).scalars().all())
    assert {"admin@seed.example.com", "s1@seed.example.com", "t1@seed.example.com"} <= emails


async def test_import_rejects_existing_email_atomic(auth_db) -> None:
    await _seed_admin(auth_db)
    async with auth_db() as s:
        s.add(
            User(
                email="dup@seed.example.com",
                password_hash=hash_password(ADMIN_PWD),
                role=UserRole.ADMIN,
                name="Dup",
                must_change_password=False,
            )
        )
        await s.commit()

    # 第二行邮箱已存在于 DB → 整批 422，第一行（合法）也不入库
    csv_bytes = "role,name,email\nSTUDENT,New1,new1@seed.example.com\nADMIN,Dup,dup@seed.example.com\n"
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await ac.post("/api/v1/auth/login", json={"email": "admin@seed.example.com", "password": ADMIN_PWD})
        r = await ac.post("/api/v1/admin/import-users", files={"file": ("u.csv", csv_bytes, "text/csv")})
        assert r.status_code == 422
        assert r.json()["detail"]["imported"] == 0

    async with auth_db() as s:
        emails = set((await s.execute(select(User.email))).scalars().all())
    assert "new1@seed.example.com" not in emails  # 原子：未插入


async def test_import_forbidden_for_student(auth_db) -> None:
    async with auth_db() as s:
        s.add(
            User(
                email="stu@seed.example.com",
                password_hash=hash_password("StuPass#1"),
                role=UserRole.STUDENT,
                name="Stu",
                must_change_password=False,
                student=Student(student_no="S1", grade=2024, major="CS"),
            )
        )
        await s.commit()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await ac.post("/api/v1/auth/login", json={"email": "stu@seed.example.com", "password": "StuPass#1"})
        r = await ac.post(
            "/api/v1/admin/import-users",
            files={"file": ("u.csv", b"role,name,email\n", "text/csv")},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "forbidden"
