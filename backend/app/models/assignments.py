"""作业、提交、成绩。文件存 MinIO（``file_key``），M6 接入对象存储。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.constants import SubmissionStatus


class Assignment(Base, TimestampMixin):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    section_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sections.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    late_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    allow_late: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    attachment_key: Mapped[str | None] = mapped_column(String(255))

    section: Mapped["Section"] = relationship(back_populates="assignments")
    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class Submission(Base):
    """学生提交。重交即更新本行（最新为准）；``submitted_at`` 随更新刷新。"""

    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "student_id", name="submissions_assignment_student_unique"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assignments.id"), index=True
    )
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.user_id"), index=True
    )
    file_key: Mapped[str | None] = mapped_column(String(255))
    text_comment: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        SAEnum(
            SubmissionStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=16,
        ),
        nullable=False,
    )

    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")
    grade: Mapped["Grade | None"] = relationship(
        back_populates="submission", uselist=False, cascade="all, delete-orphan"
    )


class Grade(Base):
    """成绩：与 Submission 1-1。"""

    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("submissions.id"), unique=True
    )
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    feedback: Mapped[str | None] = mapped_column(Text)
    graded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    graded_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True
    )

    submission: Mapped["Submission"] = relationship(back_populates="grade")
