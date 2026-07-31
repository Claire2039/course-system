"""选课记录。status ∈ {ENROLLED, WAITLISTED, DROPPED}；防超卖见 SPEC §4.1。"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.constants import EnrollmentStatus


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "section_id", name="enrollments_student_section_unique"
        ),
        # 热点查询复合索引：候补/状态扫描 & "我的选课"。其最左前缀同时覆盖
        # section_id / student_id 的单列查询，故这两列不再单列索引。
        Index("ix_enrollments_section_status", "section_id", "status"),
        Index("ix_enrollments_student_status", "student_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id")
    )
    section_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sections.id"))
    status: Mapped[EnrollmentStatus] = mapped_column(
        SAEnum(
            EnrollmentStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=16,
        ),
        nullable=False,
    )
    waitlist_position: Mapped[int | None] = mapped_column(Integer)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    student: Mapped["Student"] = relationship()
    section: Mapped["Section"] = relationship(back_populates="enrollments")
