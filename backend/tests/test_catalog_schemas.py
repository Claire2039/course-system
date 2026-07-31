"""目录 schema 的纯单元测试（无 DB）：computed available、Page 信封、序列化。"""

from app.schemas.catalog import CourseRef, Page, SectionOut, TeacherRef, TimeSlotOut


def _section(capacity: int, seats: int) -> SectionOut:
    return SectionOut(
        id=1,
        capacity=capacity,
        seats_taken=seats,
        room="R1",
        semester_id=1,
        course=CourseRef(code="CS101", title="CS", credits=3),
        teacher=TeacherRef(name="T", teacher_no="T1"),
        time_slots=[TimeSlotOut(day_of_week=1, start_period=1, end_period=2)],
    )


def test_available_computed() -> None:
    assert _section(capacity=30, seats=12).available == 18


def test_available_zero_when_full() -> None:
    assert _section(capacity=1, seats=1).available == 0


def test_available_in_serialization() -> None:
    dumped = _section(capacity=10, seats=3).model_dump()
    assert dumped["available"] == 7  # computed_field 出现在序列化结果里


def test_page_envelope_generic() -> None:
    p = Page[CourseRef](
        items=[CourseRef(code="A", title="A", credits=1)],
        total=1,
        limit=50,
        offset=0,
    )
    assert p.total == 1 and len(p.items) == 1
