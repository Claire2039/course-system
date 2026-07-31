"""用户、学生、教师模型。

``User`` 与 ``Student`` / ``Teacher`` 为 1-1（子表以 ``user_id`` 作主键 + 外键）。
角色见 :class:`~app.models.constants.UserRole`。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.constants import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=16,
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100))
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    student: Mapped["Student | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    teacher: Mapped["Teacher | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Student(Base):
    __tablename__ = "students"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), primary_key=True
    )
    student_no: Mapped[str] = mapped_column(String(32), unique=True)
    grade: Mapped[int] = mapped_column(Integer)
    major: Mapped[str] = mapped_column(String(64))

    user: Mapped["User"] = relationship(back_populates="student")


class Teacher(Base):
    __tablename__ = "teachers"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), primary_key=True
    )
    teacher_no: Mapped[str] = mapped_column(String(32), unique=True)
    department: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(64))

    user: Mapped["User"] = relationship(back_populates="teacher")
