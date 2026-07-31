"""并发零超卖测试（镇店之宝）。

capacity=1 的教学班，N=500 名学生并发抢课：断言**恰好 1 个 ENROLLED、其余 WAITLISTED、
零超卖、无死锁**；随后退课恰好顶上一名候补。需 TEST_DATABASE_URL；Redis 走 fakeredis。
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import fakeredis.aioredis
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.db.base import Base
from app.models import Course, Enrollment, Section, Semester, Student, Teacher, User
from app.models.constants import EnrollmentStatus, UserRole
from app.services import enrollment_service

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
N = 500
CONCURRENCY = 32


@pytest_asyncio.fixture
async def world():
    if not TEST_DATABASE_URL:
        pytest.skip("needs TEST_DATABASE_URL")
    engine = create_async_engine(
        TEST_DATABASE_URL, pool_size=CONCURRENCY + 5, max_overflow=10
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    now = datetime.now(timezone.utc)
    async with Session() as s:
        sem = Semester(
            name="Fall",
            is_current=True,
            enroll_open_at=now - timedelta(days=1),
            enroll_close_at=now + timedelta(days=7),
            drop_deadline=now + timedelta(days=14),
            max_credits=30,
            max_courses=8,
        )
        s.add(sem)
        tu = User(
            email="tc@seed.example.com",
            password_hash=hash_password("x"),
            role=UserRole.TEACHER,
            name="T",
            must_change_password=False,
            teacher=Teacher(teacher_no="T0001", department="CS", title="L"),
        )
        s.add(tu)
        c = Course(code="CS1", title="C", credits=3, department="CS")
        s.add(c)
        await s.flush()
        sec = Section(
            course_id=c.id,
            teacher_id=tu.teacher.user_id,
            semester_id=sem.id,
            capacity=1,
            seats_taken=0,
            room="R",
        )
        s.add(sec)
        await s.flush()
        section_id = sec.id
        ph = hash_password("p")
        for i in range(N):
            s.add(
                User(
                    email=f"c{i}@seed.example.com",
                    password_hash=ph,
                    role=UserRole.STUDENT,
                    name=f"C{i}",
                    must_change_password=False,
                    student=Student(student_no=f"S{i:05d}", grade=2024, major="CS"),
                )
            )
        await s.commit()
        student_ids = (
            await s.execute(select(User.id).where(User.role == UserRole.STUDENT))
        ).scalars().all()

    try:
        yield {"Session": Session, "section_id": section_id, "fake": fake, "student_ids": student_ids}
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
        await fake.aclose()


async def test_zero_oversell(world) -> None:
    Session = world["Session"]
    section_id = world["section_id"]
    fake = world["fake"]
    student_ids = world["student_ids"]
    sem_gate = asyncio.Semaphore(CONCURRENCY)

    async def enroll_one(sid: int):
        async with sem_gate:
            async with Session() as session:
                try:
                    return await enrollment_service.enroll(
                        session, fake, sid, section_id
                    )
                except enrollment_service.EnrollmentError:
                    return None

    results = await asyncio.gather(*(enroll_one(sid) for sid in student_ids))

    enrolled = sum(
        1 for r in results if r and r.status == EnrollmentStatus.ENROLLED
    )
    waitlisted = sum(
        1 for r in results if r and r.status == EnrollmentStatus.WAITLISTED
    )
    assert enrolled == 1, f"expected exactly 1 ENROLLED, got {enrolled}"
    assert waitlisted == N - 1, f"expected {N - 1} WAITLISTED, got {waitlisted}"

    async with Session() as s:
        sec = await s.get(Section, section_id)
        assert sec.seats_taken == 1  # 零超卖
        db_enrolled = (
            await s.execute(
                select(func.count())
                .select_from(Enrollment)
                .where(
                    Enrollment.section_id == section_id,
                    Enrollment.status == EnrollmentStatus.ENROLLED,
                )
            )
        ).scalar_one()
        assert db_enrolled == 1  # DB 与 seats_taken 一致

        enrolled_enr = (
            await s.execute(
                select(Enrollment).where(
                    Enrollment.section_id == section_id,
                    Enrollment.status == EnrollmentStatus.ENROLLED,
                )
            )
        ).scalar_one()
        enrolled_id = enrolled_enr.id
        enrolled_student = enrolled_enr.student_id

    # 退课 → 恰好顶上一名候补
    async with Session() as s:
        await enrollment_service.drop(s, fake, enrolled_student, enrolled_id)

    async with Session() as s:
        db_enrolled = (
            await s.execute(
                select(func.count())
                .select_from(Enrollment)
                .where(
                    Enrollment.section_id == section_id,
                    Enrollment.status == EnrollmentStatus.ENROLLED,
                )
            )
        ).scalar_one()
        assert db_enrolled == 1  # 转正一名，仍为 1
        sec = await s.get(Section, section_id)
        assert sec.seats_taken == 1
