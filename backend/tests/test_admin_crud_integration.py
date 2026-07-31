"""管理员 CRUD 集成测试：课程/教学班/学期 + 删除被引用 409 + is_current 唯一。"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.main import app
from app.models import Semester, Teacher, User
from app.models.constants import UserRole

pytestmark = pytest.mark.integration

ADMIN_EMAIL = "root@seed.example.com"
ADMIN_PWD = "Root#2026"


async def _seed(auth_db) -> tuple[int, int]:
    """建管理员 + 一个教师 + 一个学期；返回 (teacher_id, semester_id)。"""
    now = datetime.now(timezone.utc)
    async with auth_db() as s:
        s.add(
            User(
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PWD),
                role=UserRole.ADMIN,
                name="Root",
                must_change_password=False,
            )
        )
        tu = User(
            email="admt@seed.example.com",
            password_hash=hash_password("x"),
            role=UserRole.TEACHER,
            name="T",
            must_change_password=False,
            teacher=Teacher(teacher_no="ADM1", department="CS", title="Lecturer"),
        )
        s.add(tu)
        sem = Semester(
            name="S1",
            is_current=False,
            enroll_open_at=now,
            enroll_close_at=now + timedelta(days=30),
            drop_deadline=now + timedelta(days=60),
            max_credits=30,
            max_courses=8,
        )
        s.add(sem)
        await s.commit()
        return tu.id, sem.id


async def _login(ac: AsyncClient) -> None:
    r = await ac.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD})
    assert r.status_code == 200


async def test_course_section_crud_and_delete_guard(auth_db) -> None:
    teacher_id, semester_id = await _seed(auth_db)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac)

        r = await ac.post(
            "/api/v1/admin/courses",
            json={"code": "X101", "title": "X", "credits": 3, "department": "CS"},
        )
        assert r.status_code == 200, r.text
        cid = r.json()["id"]

        r = await ac.patch(f"/api/v1/admin/courses/{cid}", json={"title": "X-updated"})
        assert r.status_code == 200 and r.json()["title"] == "X-updated"

        r = await ac.post(
            "/api/v1/admin/sections",
            json={
                "course_id": cid,
                "teacher_id": teacher_id,
                "semester_id": semester_id,
                "capacity": 40,
                "room": "R1",
            },
        )
        assert r.status_code == 200, r.text
        sid = r.json()["id"]

        # 课程被教学班引用 → 删除 409
        assert (await ac.delete(f"/api/v1/admin/courses/{cid}")).status_code == 409
        # 删教学班 204 → 再删课程 204
        assert (await ac.delete(f"/api/v1/admin/sections/{sid}")).status_code == 204
        assert (await ac.delete(f"/api/v1/admin/courses/{cid}")).status_code == 204


async def test_semester_current_invariant(auth_db) -> None:
    _, semester_id = await _seed(auth_db)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac)
        # 新建 S2 并设为当前
        r = await ac.post(
            "/api/v1/admin/semesters",
            json={
                "name": "S2",
                "is_current": True,
                "enroll_open_at": "2026-09-01T00:00:00Z",
                "enroll_close_at": "2026-09-30T00:00:00Z",
                "drop_deadline": "2026-10-15T00:00:00Z",
                "max_credits": 30,
                "max_courses": 8,
            },
        )
        assert r.status_code == 200
        # 把 seed 的 S1 设为当前 → S2 应被自动取消（唯一 current）
        await ac.patch(f"/api/v1/admin/semesters/{semester_id}", json={"is_current": True})
        sems = (await ac.get("/api/v1/admin/semesters")).json()
        currents = [x for x in sems if x["is_current"]]
        assert len(currents) == 1
        assert currents[0]["id"] == semester_id


async def test_admin_teachers_list(auth_db) -> None:
    await _seed(auth_db)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac)
        r = await ac.get("/api/v1/admin/teachers")
        assert r.status_code == 200
        assert any(t["teacher_no"] == "ADM1" for t in r.json())
