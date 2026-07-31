"""SQLAlchemy 声明基类、约束命名约定、审计时间戳混入。

M1 的地基：所有模型继承 ``Base``；``TimestampMixin`` 提供审计列。
"""

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 确定性命名约定：让 Alembic 自动生成的迁移 diff 稳定、可复现。
# 刻意不含 "ck"：枚举列经 ``Enum(create_constraint=True)`` 生成的 CHECK 为匿名约束，
# 若约定含 ck 会因缺 ``%(constraint_name)s`` 而编译报错；显式 CHECK 直接给字面名即可。
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """``created_at`` / ``updated_at`` 审计列。

    仅用在 SPEC 未指定专属时间戳的表（semesters / courses / sections / assignments）。
    带有 SPEC 强制时间字段的表（users / enrollments / submissions / grades /
    notifications）使用各自的显式列，避免重复语义。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
