"""目录浏览集成测试：需 TEST_DATABASE_URL；Redis 走 fakeredis。

覆盖：列表/详情、computed available、当前学期默认、按 course 过滤、分页、periods、
未登录 401、404。
"""

from datetime import datetime, time, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.main import app
from app.models import Course, PeriodDef, Section, Semester, Teacher, TimeSlot, User
from app.models.constants import UserRole

pytestmark = pytest.mark.integration

VIEW_EMAIL = "view@seed.example.com"
VIEW_PWD = "ViewPass#1"


async def _seed_catalog(db) -> tuple[int, int, int]:
    now = datetime.now(timezone.utc)
    async with db() as s:
        s.add(
            User(
                email=VIEW_EMAIL,
                password_hash=hash_password(VIEW_PWD),
                role=UserRole.ADMIN,
                name="Viewer",
                must_change_password=False,
            )
        )
        sem = Semester(
            name="2025 Fall",
            is_current=True,
            enroll_open_at=now,
            enroll_close_at=now + timedelta(days=7),
            drop_deadline=now + timedelta(days=14),
            max_credits=30,
            max_courses=8,
        )
        s.add(sem)
        s.add_all(
            [
                PeriodDef(period_no=i, start_time=time(8, 0), end_time=time(8, 45))
                for i in range(1, 4)
            ]
        )
        tu = User(
            email="tcat@seed.example.com",
            password_hash=hash_password("x"),
            role=UserRole.TEACHER,
            name="Prof Cat",
            must_change_password=False,
            teacher=Teacher(teacher_no="T0001", department="CS", title="Lecturer"),
        )
        s.add(tu)
        c = Course(code="CS101", title="Intro CS", credits=3, description="intro", department="CS")
        s.add(c)
        await s.flush()
        sec = Section(
            course_id=c.id,
            teacher_id=tu.teacher.user_id,
            semester_id=sem.id,
            capacity=30,
            seats_taken=5,
            room="R1",
        )
        s.add(sec)
        await s.flush()
        s.add(TimeSlot(section_id=sec.id, day_of_week=1, start_period=1, end_period=2))
        await s.commit()
        return sem.id, c.id, sec.id


async def _login(ac: AsyncClient) -> None:
    r = await ac.post(
        "/api/v1/auth/login", json={"email": VIEW_EMAIL, "password": VIEW_PWD}
    )
    assert r.status_code == 200


async def test_catalog_endpoints(auth_db) -> None:
    _, course_id, sec_id = await _seed_catalog(auth_db)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac)

        r = await ac.get("/api/v1/courses")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 1
        assert body["items"][0]["code"] == "CS101"

        r = await ac.get(f"/api/v1/courses/{course_id}")
        assert r.status_code == 200 and r.json()["title"] == "Intro CS"

        r = await ac.get("/api/v1/courses/99999")
        assert r.status_code == 404

        r = await ac.get("/api/v1/sections")  # 默认当前学期
        assert r.status_code == 200
        sbody = r.json()
        assert sbody["total"] >= 1
        sec = sbody["items"][0]
        assert sec["capacity"] == 30 and sec["seats_taken"] == 5
        assert sec["available"] == 25  # computed
        assert sec["course"]["code"] == "CS101"
        assert sec["teacher"]["name"] == "Prof Cat"
        assert len(sec["time_slots"]) == 1

        r = await ac.get(f"/api/v1/sections?course_id={course_id}")
        assert r.json()["total"] >= 1

        r = await ac.get(f"/api/v1/sections/{sec_id}")
        assert r.status_code == 200 and r.json()["available"] == 25

        r = await ac.get("/api/v1/teachers")
        assert r.status_code == 200 and r.json()["total"] >= 1
        assert r.json()["items"][0]["name"] == "Prof Cat"

        r = await ac.get("/api/v1/periods")
        assert r.status_code == 200 and len(r.json()) == 3


async def test_catalog_requires_auth(auth_db) -> None:
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/api/v1/courses")
        assert r.status_code == 401


async def test_catalog_pagination(auth_db) -> None:
    await _seed_catalog(auth_db)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac)
        r = await ac.get("/api/v1/courses?limit=1&offset=0")
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 1
