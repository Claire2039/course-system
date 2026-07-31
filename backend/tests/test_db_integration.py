"""库内往返集成测试：需要 ``TEST_DATABASE_URL``（指向一个可丢弃的 Postgres）。

CI 不设此变量 → 自动跳过，保持 CI 绿。本地 / compose 验证：

    TEST_DATABASE_URL="postgresql+asyncpg://course:change_me_in_prod@localhost:5432/coursedb" \
      pytest -q -m integration
"""

import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import Course, Section, Semester, Student, Teacher, User
from app.models.constants import UserRole

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
_TAKE_SEAT = text(
    "UPDATE sections SET seats_taken = seats_taken + 1 "
    "WHERE id = :sid AND seats_taken < capacity"
)


@pytest_asyncio.fixture
async def db():
    if not TEST_DATABASE_URL:
        pytest.skip("needs TEST_DATABASE_URL")
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def test_user_student_roundtrip(db) -> None:
    """User↔Student 1-1：级联插入与关系回查。"""
    async with db() as session:
        user = User(
            email="stu1@x.local",
            password_hash="h",
            role=UserRole.STUDENT,
            name="Stu One",
            student=Student(student_no="S000001", grade=2024, major="CS"),
        )
        session.add(user)
        await session.commit()

        loaded = await session.get(Student, user.id)  # PK = user_id
        assert loaded is not None
        assert loaded.student_no == "S000001"
        assert loaded.user.email == "stu1@x.local"


async def test_conditional_seat_update_no_oversell(db) -> None:
    """FCFS 防超卖核心：capacity=1 时条件 UPDATE 仅允许一次扣座。"""
    async with db() as session:
        now = datetime.now(timezone.utc)
        teacher_user = User(
            email="t1@x.local",
            password_hash="h",
            role=UserRole.TEACHER,
            name="Teach One",
            teacher=Teacher(teacher_no="T0001", department="CS", title="Lecturer"),
        )
        semester = Semester(
            name="t",
            is_current=False,
            enroll_open_at=now,
            enroll_close_at=now,
            drop_deadline=now,
            max_credits=30,
            max_courses=8,
        )
        course = Course(code="T101", title="T", credits=3, department="CS")
        session.add_all([teacher_user, semester, course])
        await session.flush()

        section = Section(
            course_id=course.id,
            teacher_id=teacher_user.teacher.user_id,
            semester_id=semester.id,
            capacity=1,
            seats_taken=0,
            room="R1",
        )
        session.add(section)
        await session.flush()

        first = await session.execute(_TAKE_SEAT, {"sid": section.id})
        await session.flush()
        second = await session.execute(_TAKE_SEAT, {"sid": section.id})

        assert first.rowcount == 1   # 第一次扣座成功
        assert second.rowcount == 0  # 满了 → 第二次不再扣（零超卖）

        final = await session.execute(
            text("SELECT seats_taken FROM sections WHERE id = :sid"), {"sid": section.id}
        )
        assert final.scalar_one() == 1
