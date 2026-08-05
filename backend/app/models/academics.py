"""学期、钟点表、课程、先修课、教学班、时段。

``Section.seats_taken`` / ``capacity`` 是防超卖的核心字段，见 SPEC §4.1。
"""

from datetime import datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.constants import CourseCategory


class Semester(Base, TimestampMixin):
    __tablename__ = "semesters"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    enroll_open_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    enroll_close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    drop_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_credits: Mapped[int] = mapped_column(Integer)
    max_courses: Mapped[int] = mapped_column(Integer)

    sections: Mapped[list["Section"]] = relationship(back_populates="semester")


class PeriodDef(Base):
    """钟点表：节次号 → 起止时间，供课表渲染。"""

    __tablename__ = "period_defs"

    period_no: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class Course(Base, TimestampMixin):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    credits: Mapped[int] = mapped_column(SmallInteger)
    description: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str] = mapped_column(String(64))
    category: Mapped[CourseCategory] = mapped_column(
        SAEnum(
            CourseCategory,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=32,
        ),
        nullable=False,
    )
    syllabus: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    sections: Mapped[list["Section"]] = relationship(back_populates="course")
    # 本课要求的先修课；及本课作为哪些课的先修课（M:N 自引用）
    prerequisites: Mapped[list["CoursePrerequisite"]] = relationship(
        back_populates="course",
        foreign_keys="CoursePrerequisite.course_id",
        cascade="all, delete-orphan",
    )
    prerequisite_for: Mapped[list["CoursePrerequisite"]] = relationship(
        back_populates="prereq_course",
        foreign_keys="CoursePrerequisite.prereq_course_id",
        cascade="all, delete-orphan",
    )


class CoursePrerequisite(Base):
    """课程先修关系（复合主键）。"""

    __tablename__ = "course_prerequisites"

    course_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("courses.id"), primary_key=True
    )
    prereq_course_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("courses.id"), primary_key=True
    )

    course: Mapped["Course"] = relationship(
        back_populates="prerequisites", foreign_keys=[course_id]
    )
    prereq_course: Mapped["Course"] = relationship(
        back_populates="prerequisite_for", foreign_keys=[prereq_course_id]
    )


class Section(Base, TimestampMixin):
    """教学班：某课在某学期由某教师开的一个班，带容量与已选数。"""

    __tablename__ = "sections"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="sections_capacity_positive"),
        CheckConstraint("seats_taken >= 0", name="sections_seats_taken_nonneg"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    course_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("courses.id"), index=True
    )
    teacher_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teachers.user_id"), index=True
    )
    semester_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("semesters.id"), index=True
    )
    capacity: Mapped[int] = mapped_column(Integer)
    seats_taken: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    room: Mapped[str] = mapped_column(String(64))

    course: Mapped["Course"] = relationship(back_populates="sections")
    teacher: Mapped["Teacher"] = relationship()
    semester: Mapped["Semester"] = relationship(back_populates="sections")
    time_slots: Mapped[list["TimeSlot"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="section")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="section")


class TimeSlot(Base):
    """教学班的上课时段：周几 × 节次区间（节次号引用 period_defs）。"""

    __tablename__ = "time_slots"
    __table_args__ = (
        CheckConstraint(
            "day_of_week BETWEEN 1 AND 7", name="time_slots_day_of_week_range"
        ),
        CheckConstraint(
            "start_period <= end_period", name="time_slots_period_order"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    section_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sections.id"), index=True
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger)
    start_period: Mapped[int] = mapped_column(SmallInteger)
    end_period: Mapped[int] = mapped_column(SmallInteger)

    section: Mapped["Section"] = relationship(back_populates="time_slots")
