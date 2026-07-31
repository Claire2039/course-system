"""教师工作台集成测试：/me/sections、花名册、非拥有 403。"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.main import app
from app.models import Course, Enrollment, Section, Semester, Student, Teacher, User
from app.models.constants import EnrollmentStatus, UserRole

pytestmark = pytest.mark.integration

PWD = "Tpass#1"


async def _seed(auth_db) -> tuple[int, int, str, str]:
    """建两个教师 + 一门课 + 一个教学班(属教师A) + 一名学生已选；返回 (section_id, teacher_a_email, teacher_b_email)."""
    now = datetime.now(timezone.utc)
    async with auth_db() as s:
        sem = Semester(
            name="S",
            is_current=True,
            enroll_open_at=now - timedelta(days=1),
            enroll_close_at=now + timedelta(days=7),
            drop_deadline=now + timedelta(days=14),
            max_credits=30,
            max_courses=8,
        )
        s.add(sem)
        ta = User(
            email="ta@seed.example.com",
            password_hash=hash_password(PWD),
            role=UserRole.TEACHER,
            name="TA",
            must_change_password=False,
            teacher=Teacher(teacher_no="TA1", department="CS", title="L"),
        )
        s.add(ta)
        tb = User(
            email="tb@seed.example.com",
            password_hash=hash_password(PWD),
            role=UserRole.TEACHER,
            name="TB",
            must_change_password=False,
            teacher=Teacher(teacher_no="TB1", department="CS", title="L"),
        )
        s.add(tb)
        c = Course(code="T201", title="Teach", credits=3, department="CS")
        s.add(c)
        await s.flush()
        sec = Section(
            course_id=c.id,
            teacher_id=ta.id,
            semester_id=sem.id,
            capacity=50,
            seats_taken=1,
            room="R",
        )
        s.add(sec)
        su = User(
            email="ts@seed.example.com",
            password_hash=hash_password("x"),
            role=UserRole.STUDENT,
            name="TS",
            must_change_password=False,
            student=Student(student_no="TSA1", grade=2024, major="CS"),
        )
        s.add(su)
        await s.flush()
        s.add(Enrollment(student_id=su.id, section_id=sec.id, status=EnrollmentStatus.ENROLLED))
        await s.commit()
        return sec.id, "ta@seed.example.com", "tb@seed.example.com"


async def _login(ac: AsyncClient, email: str) -> None:
    r = await ac.post("/api/v1/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200


async def test_my_sections_and_roster(auth_db) -> None:
    sec_id, teacher_a, _ = await _seed(auth_db)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, teacher_a)
        r = await ac.get("/api/v1/me/sections")
        assert r.status_code == 200 and len(r.json()) == 1
        item = r.json()[0]
        assert item["course"]["code"] == "T201"
        assert item["enrolled_count"] == 1

        r = await ac.get(f"/api/v1/sections/{sec_id}/roster")
        assert r.status_code == 200 and len(r.json()) == 1
        assert r.json()[0]["student_no"] == "TSA1"


async def test_roster_forbidden_for_non_owner(auth_db) -> None:
    sec_id, _, teacher_b = await _seed(auth_db)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, teacher_b)
        r = await ac.get(f"/api/v1/sections/{sec_id}/roster")
        assert r.status_code == 403
