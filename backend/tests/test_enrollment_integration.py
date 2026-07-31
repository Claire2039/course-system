"""选课引擎集成测试：需 TEST_DATABASE_URL；Redis 走 fakeredis。

覆盖：选课成功/重复 409、候补、退课转正、时间冲突 409、窗口外 403、学分上限 409。
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.main import app
from app.models import Course, Section, Semester, Student, Teacher, TimeSlot, User
from app.models.constants import UserRole

pytestmark = pytest.mark.integration

PWD = "StuPass#1"


async def _sem_teacher(db, window="open", max_credits=30, max_courses=8, tag="A"):
    now = datetime.now(timezone.utc)
    if window == "closed":
        open_at, close_at = now - timedelta(days=10), now - timedelta(days=1)
    else:
        open_at, close_at = now - timedelta(days=1), now + timedelta(days=7)
    async with db() as s:
        sem = Semester(
            name="Fall",
            is_current=True,
            enroll_open_at=open_at,
            enroll_close_at=close_at,
            drop_deadline=now + timedelta(days=14),
            max_credits=max_credits,
            max_courses=max_courses,
        )
        s.add(sem)
        tu = User(
            email=f"t{tag}@seed.example.com",
            password_hash=hash_password("x"),
            role=UserRole.TEACHER,
            name="T",
            must_change_password=False,
            teacher=Teacher(teacher_no=f"T{tag}", department="CS", title="Lecturer"),
        )
        s.add(tu)
        await s.commit()
        return sem.id, tu.teacher.user_id


async def _add_section(
    db, sem_id, teacher_id, *, code, capacity, credits=3, day=1, sp=1, ep=2
):
    async with db() as s:
        c = Course(code=code, title=code, credits=credits, department="CS")
        s.add(c)
        await s.flush()
        sec = Section(
            course_id=c.id,
            teacher_id=teacher_id,
            semester_id=sem_id,
            capacity=capacity,
            seats_taken=0,
            room="R1",
        )
        s.add(sec)
        if day:
            s.add(TimeSlot(section_id=sec.id, day_of_week=day, start_period=sp, end_period=ep))
        await s.commit()
        return sec.id


async def _student(db, email: str) -> None:
    async with db() as s:
        s.add(
            User(
                email=email,
                password_hash=hash_password(PWD),
                role=UserRole.STUDENT,
                name=email.split("@")[0],
                must_change_password=False,
                student=Student(student_no="S" + email[1:7], grade=2024, major="CS"),
            )
        )
        await s.commit()


async def _login(ac: AsyncClient, email: str) -> None:
    r = await ac.post("/api/v1/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text


async def test_enroll_already_and_drop_promotes(auth_db) -> None:
    sem_id, teacher_id = await _sem_teacher(auth_db, tag="P")
    sec_id = await _add_section(auth_db, sem_id, teacher_id, code="P1", capacity=1)
    await _student(auth_db, "s1@seed.example.com")
    await _student(auth_db, "s2@seed.example.com")

    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, "s1@seed.example.com")
        r = await ac.post(f"/api/v1/sections/{sec_id}/enroll")
        assert r.status_code == 200 and r.json()["status"] == "ENROLLED"

        r = await ac.post(f"/api/v1/sections/{sec_id}/enroll")  # 重复
        assert r.status_code == 409 and r.json()["detail"]["code"] == "already_enrolled"

        r = await ac.get("/api/v1/me/enrollments")
        enr_id = r.json()[0]["id"]

    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, "s2@seed.example.com")
        r = await ac.post(f"/api/v1/sections/{sec_id}/enroll")
        assert r.json()["status"] == "WAITLISTED"
        r = await ac.get("/api/v1/me/waitlist")
        assert len(r.json()) == 1

    async with AsyncClient(app=app, base_url="http://test") as ac:  # s1 退课
        await _login(ac, "s1@seed.example.com")
        r = await ac.delete(f"/api/v1/enrollments/{enr_id}")
        assert r.status_code == 200

    async with AsyncClient(app=app, base_url="http://test") as ac:  # s2 转正
        await _login(ac, "s2@seed.example.com")
        r = await ac.get("/api/v1/me/enrollments")
        assert r.status_code == 200 and len(r.json()) == 1
        r = await ac.get("/api/v1/me/waitlist")
        assert len(r.json()) == 0


async def test_time_conflict_409(auth_db) -> None:
    sem_id, teacher_id = await _sem_teacher(auth_db, tag="T")
    sec1 = await _add_section(auth_db, sem_id, teacher_id, code="T1", capacity=10, day=1, sp=1, ep=2)
    sec2 = await _add_section(auth_db, sem_id, teacher_id, code="T2", capacity=10, day=1, sp=1, ep=2)
    await _student(auth_db, "s1@seed.example.com")
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, "s1@seed.example.com")
        assert (await ac.post(f"/api/v1/sections/{sec1}/enroll")).status_code == 200
        r = await ac.post(f"/api/v1/sections/{sec2}/enroll")
        assert r.status_code == 409 and r.json()["detail"]["code"] == "time_conflict"


async def test_window_closed_403(auth_db) -> None:
    sem_id, teacher_id = await _sem_teacher(auth_db, window="closed", tag="W")
    sec_id = await _add_section(auth_db, sem_id, teacher_id, code="W1", capacity=10)
    await _student(auth_db, "s1@seed.example.com")
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, "s1@seed.example.com")
        r = await ac.post(f"/api/v1/sections/{sec_id}/enroll")
        assert r.status_code == 403 and r.json()["detail"]["code"] == "window_closed"


async def test_credit_cap_409(auth_db) -> None:
    sem_id, teacher_id = await _sem_teacher(auth_db, max_credits=2, tag="C")
    sec_id = await _add_section(auth_db, sem_id, teacher_id, code="C1", capacity=10, credits=3)
    await _student(auth_db, "s1@seed.example.com")
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, "s1@seed.example.com")
        r = await ac.post(f"/api/v1/sections/{sec_id}/enroll")
        assert r.status_code == 409 and r.json()["detail"]["code"] == "max_credits_exceeded"


async def test_reenroll_after_drop(auth_db) -> None:
    # 退课后重新选课应复用 DROPPED 行，而非触发 (student, section) 唯一约束冲突。
    sem_id, teacher_id = await _sem_teacher(auth_db, tag="R")
    sec_id = await _add_section(auth_db, sem_id, teacher_id, code="R1", capacity=10)
    await _student(auth_db, "s1@seed.example.com")
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, "s1@seed.example.com")
        r = await ac.post(f"/api/v1/sections/{sec_id}/enroll")
        assert r.status_code == 200 and r.json()["status"] == "ENROLLED"
        eid = (await ac.get("/api/v1/me/enrollments")).json()[0]["id"]
        assert (await ac.delete(f"/api/v1/enrollments/{eid}")).status_code == 200
        # 重新选 → 复用 DROPPED 行 → ENROLLED
        r = await ac.post(f"/api/v1/sections/{sec_id}/enroll")
        assert r.status_code == 200 and r.json()["status"] == "ENROLLED"
        assert len((await ac.get("/api/v1/me/enrollments")).json()) == 1
