"""种子数据脚本：一键生成可演示的初始数据集。

在 api 容器内运行（镜像已含本脚本与依赖、且可连 DB）：

    python -m scripts.seed_data            # 已有"当前学期"则跳过（幂等）
    python -m scripts.seed_data --reset    # 清空全部表后重建

生成内容（见 SPEC §7）：12 钟点 / 1 ADMIN / 20 教师 / 2000 学生 / 1 当前学期
（选课窗口已开）/ 30 课程 / 若干先修边 / ~45 教学班（含 1 个 capacity=1 用于零超卖演示）/
若干时段。enrollments 等运行期数据不在种子内（M4+ 产生）。

所有学生与教师共用一个初始口令（argon2 仅哈希一次并复用），首登强制改密；ADMIN
使用独立已知口令、不强制改密以便演示登录。
"""

import argparse
import asyncio
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models import (  # noqa: F401  导入即注册模型
    Course,
    CoursePrerequisite,
    PeriodDef,
    Section,
    Semester,
    Student,
    Teacher,
    TimeSlot,
    User,
)
from app.models.constants import UserRole

# ---------- 生成参数 ----------
DEPARTMENTS = ["CS", "SE", "AI", "MA", "EE", "BU"]
TEACHER_TITLES = ["Lecturer", "Associate Professor", "Professor"]
GRADES = [2022, 2023, 2024, 2025]
CREDIT_OPTIONS = [3, 4, 2, 3, 4]
CAPACITY_TIERS = [30, 60, 120]

PERIOD_COUNT = 12
TEACHER_COUNT = 20
STUDENT_COUNT = 2000
COURSES_PER_DEPT = 5  # 6 dept × 5 = 30
BATCH_SIZE = 500

INITIAL_PASSWORD = "InitPass#2026"  # 所有学生/教师共用，首登强制改
ADMIN_EMAIL = "admin@seed.example.com"
ADMIN_PASSWORD = "Admin#2026"  # 演示账号，可直登


# ---------- 工具 ----------
def _hash_password(plain: str) -> str:
    """argon2 哈希。种子期仅调用两次（学生共享串 + ADMIN）。"""
    from argon2 import PasswordHasher

    return PasswordHasher().hash(plain)


def _period_times() -> list[tuple[int, time, time]]:
    """12 节：每节 45 分钟，自 08:00 起，节间 10 分钟。"""
    start = datetime(2000, 1, 1, 8, 0)
    slot = timedelta(minutes=45)
    gap = timedelta(minutes=10)
    out: list[tuple[int, time, time]] = []
    cur = start
    for i in range(PERIOD_COUNT):
        nxt = cur + slot
        out.append((i + 1, cur.time(), nxt.time()))
        cur = nxt + gap
    return out


# ---------- 幂等 / 重置 ----------
async def _already_seeded(session: AsyncSession) -> bool:
    res = await session.execute(select(Semester.id).where(Semester.is_current.is_(True)).limit(1))
    return res.first() is not None


async def _reset(session: AsyncSession) -> None:
    # 反依赖序清空全部表，重置自增序列。
    await session.execute(
        text(
            "TRUNCATE TABLE notifications, grades, submissions, assignments, enrollments, "
            "time_slots, sections, course_prerequisites, courses, period_defs, semesters, "
            "teachers, students, users RESTART IDENTITY CASCADE"
        )
    )
    await session.commit()


# ---------- 各实体播种 ----------
async def _seed_period_defs(session: AsyncSession) -> None:
    session.add_all(
        PeriodDef(period_no=n, start_time=s, end_time=e) for n, s, e in _period_times()
    )
    await session.flush()


async def _seed_admin(session: AsyncSession, admin_hash: str) -> None:
    session.add(
        User(
            email=ADMIN_EMAIL,
            password_hash=admin_hash,
            role=UserRole.ADMIN,
            name="System Admin",
            must_change_password=False,
        )
    )
    await session.flush()


async def _seed_teachers(session: AsyncSession, shared_hash: str) -> list[Teacher]:
    users: list[User] = []
    for i in range(TEACHER_COUNT):
        idx = i + 1
        users.append(
            User(
                email=f"teacher{idx:04d}@seed.example.com",
                password_hash=shared_hash,
                role=UserRole.TEACHER,
                name=f"Teacher {idx:04d}",
                must_change_password=True,
                teacher=Teacher(
                    teacher_no=f"T{idx:04d}",
                    department=DEPARTMENTS[i % len(DEPARTMENTS)],
                    title=TEACHER_TITLES[i % len(TEACHER_TITLES)],
                ),
            )
        )
    session.add_all(users)
    await session.flush()
    return [u.teacher for u in users]  # type: ignore[list-item]


async def _seed_students(session: AsyncSession, shared_hash: str) -> None:
    batch: list[User] = []
    for i in range(STUDENT_COUNT):
        idx = i + 1
        batch.append(
            User(
                email=f"student{idx:04d}@seed.example.com",
                password_hash=shared_hash,
                role=UserRole.STUDENT,
                name=f"Student {idx:04d}",
                must_change_password=True,
                student=Student(
                    student_no=f"S{idx:06d}",
                    grade=GRADES[i % len(GRADES)],
                    major=DEPARTMENTS[i % len(DEPARTMENTS)],
                ),
            )
        )
        if len(batch) >= BATCH_SIZE:
            session.add_all(batch)
            await session.flush()
            batch.clear()
    if batch:
        session.add_all(batch)
        await session.flush()


async def _seed_semester(session: AsyncSession) -> Semester:
    now = datetime.now(timezone.utc)
    semester = Semester(
        name="2025–2026 Fall",
        is_current=True,
        enroll_open_at=now - timedelta(days=1),    # 已开
        enroll_close_at=now + timedelta(days=7),   # 7 天后关 → 窗口开启
        drop_deadline=now + timedelta(days=14),
        max_credits=30,
        max_courses=8,
    )
    session.add(semester)
    await session.flush()
    return semester


async def _seed_courses(session: AsyncSession) -> list[Course]:
    courses: list[Course] = []
    for dept in DEPARTMENTS:
        for k in range(COURSES_PER_DEPT):
            level = 100 * (k + 1) + 1  # 101, 201, 301, 401, 501
            courses.append(
                Course(
                    code=f"{dept}{level}",
                    title=f"{dept} {level}",
                    credits=CREDIT_OPTIONS[k % len(CREDIT_OPTIONS)],
                    description=f"{dept} 系课程 {level}。",
                    department=dept,
                )
            )
    session.add_all(courses)
    await session.flush()
    return courses


async def _seed_prerequisites(session: AsyncSession, courses: list[Course]) -> None:
    # 仅"向后"边（prereq 索引 < course 索引），保证无环。
    edges: set[tuple[int, int]] = set()
    for i in range(2, len(courses), 3):
        edges.add((i, i - 1))
    for i in range(0, len(courses) - 6, 6):
        edges.add((i + 6, i))
    for ci, pi in sorted(edges):
        session.add(
            CoursePrerequisite(course_id=courses[ci].id, prereq_course_id=courses[pi].id)
        )
    await session.flush()


async def _seed_sections(
    session: AsyncSession,
    courses: list[Course],
    teachers: list[Teacher],
    semester: Semester,
) -> list[Section]:
    sections: list[Section] = []
    sid = 0
    for ci, course in enumerate(courses):
        count = 2 if ci % 3 == 0 else 1  # 每 3 门课有一门开 2 个班
        for _ in range(count):
            teacher = teachers[sid % len(teachers)]
            sections.append(
                Section(
                    course_id=course.id,
                    teacher_id=teacher.user_id,
                    semester_id=semester.id,
                    capacity=CAPACITY_TIERS[sid % len(CAPACITY_TIERS)],
                    seats_taken=0,
                    room=f"TB/{(sid % 5) + 1}/{100 + sid}",
                )
            )
            sid += 1
    # 专门留一个 capacity=1 的班，供 M4 并发零超卖演示。
    sections.append(
        Section(
            course_id=courses[0].id,
            teacher_id=teachers[0].user_id,
            semester_id=semester.id,
            capacity=1,
            seats_taken=0,
            room="TB/1/1",
        )
    )
    session.add_all(sections)
    await session.flush()
    return sections


async def _seed_time_slots(session: AsyncSession, sections: list[Section]) -> None:
    slots: list[TimeSlot] = []
    for k, sec in enumerate(sections):
        day = (k % 5) + 1
        sp = (k % 10) + 1
        slots.append(
            TimeSlot(section_id=sec.id, day_of_week=day, start_period=sp, end_period=sp + 1)
        )
        if k % 2 == 0:  # 约一半的班再追加一个时段
            slots.append(
                TimeSlot(
                    section_id=sec.id,
                    day_of_week=(day % 5) + 1,
                    start_period=((k + 3) % 10) + 1,
                    end_period=((k + 3) % 10) + 2,
                )
            )
    session.add_all(slots)
    await session.flush()


# ---------- 入口 ----------
async def main(reset: bool) -> None:
    async with AsyncSessionLocal() as session:
        if reset:
            await _reset(session)
            # _reset 已 commit；继续在同一个 session 内播种。
        elif await _already_seeded(session):
            print("已存在当前学期，跳过播种。使用 --reset 强制重建。")
            return

        shared_hash = _hash_password(INITIAL_PASSWORD)
        admin_hash = _hash_password(ADMIN_PASSWORD)

        await _seed_period_defs(session)
        await _seed_admin(session, admin_hash)
        teachers = await _seed_teachers(session, shared_hash)
        await _seed_students(session, shared_hash)
        semester = await _seed_semester(session)
        courses = await _seed_courses(session)
        await _seed_prerequisites(session, courses)
        sections = await _seed_sections(session, courses, teachers, semester)
        await _seed_time_slots(session, sections)

        await session.commit()

    print("✅ 播种完成。")
    print(f"   ADMIN 登录：{ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"   学生/教师 初始口令：{INITIAL_PASSWORD}（首登强制改密）")
    print(f"   教师数={TEACHER_COUNT}  学生数={STUDENT_COUNT}  课程数={len(courses)}  "
          f"教学班数={len(sections)}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成选课系统种子数据。")
    parser.add_argument(
        "--reset", action="store_true", help="清空全部表后重建（RESTART IDENTITY CASCADE）。"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(args.reset))
