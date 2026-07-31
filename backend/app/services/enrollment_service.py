"""选课引擎（FCFS，零超卖）。

核心不变量：座位计数权威永远在 PostgreSQL；并发下绝不超卖由条件原子 UPDATE 保证：
``UPDATE sections SET seats_taken = seats_taken + 1 WHERE id = :sid AND seats_taken < capacity``。
Redis 仅做快速门槛（挡羊群）与限流，非权威。候补 FIFO 按 (waitlist_position, id) 排序，
位次 best-effort（并发下偶有重复，由 id 兜底）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import redis.asyncio as redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Course, CoursePrerequisite, Enrollment, Section, Semester, TimeSlot
from app.models.constants import EnrollmentStatus
from app.services.notification import notify, publish_event
from app.services.ratelimit import check_rate_limit

_ENROLLED = EnrollmentStatus.ENROLLED
_WAITLISTED = EnrollmentStatus.WAITLISTED
_DROPPED = EnrollmentStatus.DROPPED

_TAKE_SEAT = text(
    "UPDATE sections SET seats_taken = seats_taken + 1 "
    "WHERE id = :sid AND seats_taken < capacity RETURNING seats_taken"
)
_FREE_SEAT = text(
    "UPDATE sections SET seats_taken = seats_taken - 1 "
    "WHERE id = :sid AND seats_taken > 0"
)


class EnrollmentError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class EnrollmentResult:
    status: EnrollmentStatus
    enrollment_id: int
    position: int | None


# ---------- 纯逻辑：时间冲突 ----------
def slots_conflict(
    a: list[tuple[int, int, int]], b: list[tuple[int, int, int]]
) -> bool:
    """两组时段 (day_of_week, start_period, end_period) 是否在同日区间重叠。"""
    for d1, s1, e1 in a:
        for d2, s2, e2 in b:
            if d1 == d2 and s1 < e2 and s2 < e1:
                return True
    return False


# ---------- Redis 门槛 ----------
async def _redis_says_full(client: redis.Redis | None, section_id: int) -> bool:
    if client is None:
        return False
    try:
        data = await client.hgetall(f"section:{section_id}:seats")
        if not data:
            return False
        return int(data.get("seats_taken", 0)) >= int(data.get("capacity", 0))
    except Exception:
        return False


async def _refresh_snapshot(
    client: redis.Redis | None, section_id: int, capacity: int, seats_taken: int
) -> None:
    if client is None:
        return
    try:
        await client.hset(
            f"section:{section_id}:seats",
            mapping={"capacity": capacity, "seats_taken": seats_taken},
        )
    except Exception:
        pass


async def _next_waitlist_position(session: AsyncSession, section_id: int) -> int:
    res = await session.execute(
        select(func.coalesce(func.max(Enrollment.waitlist_position), 0)).where(
            Enrollment.section_id == section_id, Enrollment.status == _WAITLISTED
        )
    )
    return int(res.scalar_one()) + 1


# ---------- 校验 ----------
async def _check_prereqs(
    session: AsyncSession, student_id: int, section: Section
) -> None:
    prereq_ids = (
        await session.execute(
            select(CoursePrerequisite.prereq_course_id).where(
                CoursePrerequisite.course_id == section.course_id
            )
        )
    ).scalars().all()
    if not prereq_ids:
        return
    # M4 代理：先修课"已满足"= 该生在任意学期有该先修课的 ENROLLED 记录。
    enrolled_course_ids = set(
        (
            await session.execute(
                select(Section.course_id)
                .join(Enrollment, Enrollment.section_id == Section.id)
                .where(
                    Enrollment.student_id == student_id,
                    Enrollment.status == _ENROLLED,
                )
            )
        ).scalars().all()
    )
    if any(pid not in enrolled_course_ids for pid in prereq_ids):
        raise EnrollmentError(409, "prereq_unmet", "先修课未满足。")


async def _check_caps(
    session: AsyncSession, student_id: int, semester: Semester, section: Section
) -> None:
    rows = (
        await session.execute(
            select(Course.credits)
            .join(Section, Section.course_id == Course.id)
            .join(Enrollment, Enrollment.section_id == Section.id)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.status == _ENROLLED,
                Section.semester_id == semester.id,
            )
        )
    ).scalars().all()
    count = len(rows)
    total_credits = sum(rows)
    if count + 1 > semester.max_courses:
        raise EnrollmentError(409, "max_courses_exceeded", "超过本学期选课门数上限。")
    if total_credits + section.course.credits > semester.max_credits:
        raise EnrollmentError(409, "max_credits_exceeded", "超过本学期学分上限。")


async def _check_time_conflict(
    session: AsyncSession, student_id: int, section: Section, semester: Semester
) -> None:
    target = [(t.day_of_week, t.start_period, t.end_period) for t in section.time_slots]
    if not target:
        return
    rows = (
        await session.execute(
            select(TimeSlot.day_of_week, TimeSlot.start_period, TimeSlot.end_period)
            .join(Section, TimeSlot.section_id == Section.id)
            .join(Enrollment, Enrollment.section_id == Section.id)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.status == _ENROLLED,
                Section.semester_id == semester.id,
            )
        )
    ).all()
    enrolled = [(r[0], r[1], r[2]) for r in rows]
    if slots_conflict(target, enrolled):
        raise EnrollmentError(409, "time_conflict", "与已选课程时间冲突。")


# ---------- 选课 ----------
async def enroll(
    session: AsyncSession,
    client: redis.Redis | None,
    student_id: int,
    section_id: int,
) -> EnrollmentResult:
    # 0. 限流
    if client is not None and not await check_rate_limit(client, student_id):
        raise EnrollmentError(429, "rate_limited", "选课过于频繁，请稍后再试。")
    redis_full = await _redis_says_full(client, section_id)

    async with session.begin():
        section = (
            await session.execute(
                select(Section)
                .options(selectinload(Section.course), selectinload(Section.time_slots))
                .where(Section.id == section_id)
            )
        ).scalar_one_or_none()
        if section is None:
            raise EnrollmentError(404, "section_not_found", "教学班不存在。")
        semester = await session.get(Semester, section.semester_id)
        if semester is None:
            raise EnrollmentError(409, "no_semester", "教学班未关联学期。")

        now = datetime.now(timezone.utc)
        if not (semester.enroll_open_at <= now <= semester.enroll_close_at):
            raise EnrollmentError(403, "window_closed", "不在选课开放窗口内。")

        existing = (
            await session.execute(
                select(Enrollment).where(
                    Enrollment.student_id == student_id,
                    Enrollment.section_id == section_id,
                )
            )
        ).scalar_one_or_none()
        if existing and existing.status in (_ENROLLED, _WAITLISTED):
            raise EnrollmentError(
                409,
                "already_enrolled",
                "已选过该教学班。" if existing.status == _ENROLLED else "已在候补队列中。",
            )

        await _check_prereqs(session, student_id, section)
        await _check_caps(session, student_id, semester, section)
        await _check_time_conflict(session, student_id, section, semester)

        # 条件原子扣座（权威）；Redis 显示满时跳过，直接候补。
        if redis_full:
            status, new_seats = _WAITLISTED, section.seats_taken
        else:
            taken = (
                await session.execute(_TAKE_SEAT, {"sid": section_id})
            ).scalar_one_or_none()
            if taken is not None:
                status, new_seats = _ENROLLED, int(taken)
            else:
                status, new_seats = _WAITLISTED, section.seats_taken

        position: int | None = None
        if status == _WAITLISTED:
            position = await _next_waitlist_position(session, section_id)

        if existing is not None:  # 曾 DROPPED → 复用该行，避免 (student, section) 唯一约束冲突
            enr = existing
            enr.status = status
            enr.waitlist_position = position
        else:
            enr = Enrollment(
                student_id=student_id,
                section_id=section_id,
                status=status,
                waitlist_position=position,
            )
            session.add(enr)
        await session.flush()
        enrollment_id = enr.id

        await notify(
            session,
            student_id,
            "enrolled" if status == _ENROLLED else "waitlisted",
            {"section_id": section_id, "position": position},
        )
        result = EnrollmentResult(status, enrollment_id, position)

    # 提交后：刷新门槛快照 + 发布通知（best-effort）
    await _refresh_snapshot(client, section_id, section.capacity, new_seats)
    await publish_event(
        client,
        student_id,
        "enrolled" if result.status == _ENROLLED else "waitlisted",
        {"section_id": section_id, "position": result.position},
    )
    return result


# ---------- 退课 + 候补顶上 ----------
async def _promote_next(
    session: AsyncSession, section_id: int, semester: Semester
) -> int | None:
    """取队首候补，重校验后条件扣座升为 ENROLLED；不满足则置 DROPPED 并顺延。返回被顶上的 student_id。"""
    candidates = (
        await session.execute(
            select(Enrollment)
            .where(Enrollment.section_id == section_id, Enrollment.status == _WAITLISTED)
            .order_by(Enrollment.waitlist_position, Enrollment.id)
        )
    ).scalars().all()
    for cand in candidates:
        section = (
            await session.execute(
                select(Section)
                .options(selectinload(Section.course), selectinload(Section.time_slots))
                .where(Section.id == section_id)
            )
        ).scalar_one()
        try:
            await _check_prereqs(session, cand.student_id, section)
            await _check_caps(session, cand.student_id, semester, section)
            await _check_time_conflict(session, cand.student_id, section, semester)
        except EnrollmentError:
            cand.status = _DROPPED
            cand.waitlist_position = None
            continue
        taken = (
            await session.execute(_TAKE_SEAT, {"sid": section_id})
        ).scalar_one_or_none()
        if taken is not None:
            cand.status = _ENROLLED
            cand.waitlist_position = None
            return cand.student_id
        return None  # 座位又被占满（理论不应发生，刚释放一个）
    return None


async def drop(
    session: AsyncSession,
    client: redis.Redis | None,
    student_id: int,
    enrollment_id: int,
) -> None:
    async with session.begin():
        enr = await session.get(Enrollment, enrollment_id)
        if enr is None:
            raise EnrollmentError(404, "enrollment_not_found", "选课记录不存在。")
        if enr.student_id != student_id:
            raise EnrollmentError(403, "forbidden", "不能退他人的课。")
        if enr.status == _DROPPED:
            raise EnrollmentError(409, "already_dropped", "该课已退。")

        section = await session.get(Section, enr.section_id)
        semester = await session.get(Semester, section.semester_id)
        now = datetime.now(timezone.utc)
        if now > semester.drop_deadline:
            raise EnrollmentError(403, "drop_deadline_passed", "已过退课截止时间。")

        was_enrolled = enr.status == _ENROLLED
        promoted_student: int | None = None
        enr.status = _DROPPED
        enr.waitlist_position = None

        if was_enrolled:
            await session.execute(_FREE_SEAT, {"sid": section.id})
            promoted_student = await _promote_next(session, section.id, semester)

        await notify(session, student_id, "dropped", {"section_id": section.id})
        if promoted_student is not None:
            await notify(
                session, promoted_student, "promoted", {"section_id": section.id}
            )

    # 提交后 best-effort 通知
    await publish_event(client, student_id, "dropped", {"section_id": section.id})
    if promoted_student is not None:
        await publish_event(
            client, promoted_student, "promoted", {"section_id": section.id}
        )
