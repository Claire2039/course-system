"""模型元数据 / 关系 / 约束冒烟测试。

完全不需要 DB（仅检视 ``Base.metadata`` 与映射器配置），CI 可直接跑。
真正的库内往返由 ``test_db_integration``（需 ``TEST_DATABASE_URL``）覆盖。
"""

import pytest
from sqlalchemy import BigInteger, CheckConstraint, Enum, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from app.db.base import Base
from app.models import (  # noqa: F401  导入即触发全部模型注册
    Assignment,
    Course,
    CoursePrerequisite,
    Enrollment,
    Grade,
    Notification,
    PeriodDef,
    Section,
    Semester,
    Student,
    Submission,
    Teacher,
    TimeSlot,
    User,
)

EXPECTED_TABLES = {
    "users",
    "students",
    "teachers",
    "semesters",
    "period_defs",
    "courses",
    "course_prerequisites",
    "sections",
    "time_slots",
    "enrollments",
    "assignments",
    "submissions",
    "grades",
    "notifications",
}


@pytest.fixture(autouse=True, scope="module")
def _configured() -> None:
    configure_mappers()


def _table(name: str):
    return Base.metadata.tables[name]


def _uq_names(table_name: str) -> set[str]:
    return {
        c.name
        for c in _table(table_name).constraints
        if isinstance(c, UniqueConstraint)
    }


def _ck_names(table_name: str) -> set[str]:
    return {
        c.name
        for c in _table(table_name).constraints
        if isinstance(c, CheckConstraint)
    }


def _index_names(table_name: str) -> set[str]:
    return {ix.name for ix in _table(table_name).indexes}


def test_all_tables_present() -> None:
    assert EXPECTED_TABLES <= set(Base.metadata.tables.keys())


def test_surrogate_identity_pks() -> None:
    for name in (
        "users",
        "semesters",
        "courses",
        "sections",
        "time_slots",
        "enrollments",
        "assignments",
        "submissions",
        "grades",
        "notifications",
    ):
        pk_cols = [c.name for c in _table(name).primary_key]
        assert pk_cols == ["id"], f"{name} pk = {pk_cols}"
        assert isinstance(_table(name).c.id.type, BigInteger), name


def test_natural_and_composite_pks() -> None:
    assert [c.name for c in _table("students").primary_key] == ["user_id"]
    assert [c.name for c in _table("teachers").primary_key] == ["user_id"]
    assert [c.name for c in _table("period_defs").primary_key] == ["period_no"]
    assert set(_table("course_prerequisites").primary_key.columns.keys()) == {
        "course_id",
        "prereq_course_id",
    }


def test_seats_taken_invariants() -> None:
    """防超卖核心字段：NOT NULL、server_default 0、CHECK >=0。"""
    col = _table("sections").c.seats_taken
    assert col.nullable is False
    assert col.server_default is not None
    assert "0" in str(col.server_default.arg)
    assert "sections_seats_taken_nonneg" in _ck_names("sections")
    assert "sections_capacity_positive" in _ck_names("sections")


def test_time_slot_checks() -> None:
    cks = _ck_names("time_slots")
    assert "time_slots_day_of_week_range" in cks
    assert "time_slots_period_order" in cks


def test_enum_columns_are_varchar_with_check() -> None:
    for col in (User.__table__.c.role, Enrollment.__table__.c.status):
        assert isinstance(col.type, Enum)
        assert col.type.native_enum is False
        assert col.type.create_constraint is True


def test_unique_constraints() -> None:
    # 单列唯一（约定命名）
    assert "uq_users_email" in _uq_names("users")
    assert "uq_students_student_no" in _uq_names("students")
    assert "uq_teachers_teacher_no" in _uq_names("teachers")
    assert "uq_courses_code" in _uq_names("courses")
    # 复合唯一（显式命名）
    assert "enrollments_student_section_unique" in _uq_names("enrollments")
    assert "submissions_assignment_student_unique" in _uq_names("submissions")
    # 1-1：grades.submission_id 唯一
    assert "uq_grades_submission_id" in _uq_names("grades")


def test_hot_composite_indexes() -> None:
    en_ix = _index_names("enrollments")
    assert "ix_enrollments_section_status" in en_ix
    assert "ix_enrollments_student_status" in en_ix
    assert "ix_notifications_user_created" in _index_names("notifications")


def test_one_to_one_relationships() -> None:
    assert User.student.property.uselist is False
    assert User.teacher.property.uselist is False
    assert Grade.submission.property.uselist is False
    assert Submission.grade.property.uselist is False


def test_relationships_resolve() -> None:
    # 这些访问本身即证明映射器配置成功、跨模块字符串引用全部解析。
    assert {c.name for c in Section.__table__.c} >= {
        "course_id",
        "teacher_id",
        "semester_id",
    }
    assert Enrollment.section.property.mapper.class_ is Section
    assert Assignment.section.property.mapper.class_ is Section
    assert Notification.user.property.mapper.class_ is User
