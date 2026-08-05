"""course enrichment: category, syllabus, cover_url; teacher CV fields

Revision ID: 0003
Revisives: 0002
Create Date: 2026-08-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 课程：性质 / 教学进度(JSONB) / 封面
    op.add_column(
        "courses",
        sa.Column(
            "category",
            sa.Enum(
                "通识教育课",
                "公共基础必修课",
                "专业必修课",
                "专业选修课",
                "通识选修课",
                native_enum=False,
                create_constraint=True,
                length=32,
                name="course_category",
            ),
            nullable=False,
            server_default=sa.text("'通识选修课'"),
        ),
    )
    op.add_column(
        "courses",
        sa.Column("syllabus", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "courses", sa.Column("cover_url", sa.String(length=255), nullable=True)
    )

    # 教师：研究方向 / 教育经历(JSONB) / 文献成果(JSONB)
    op.add_column(
        "teachers", sa.Column("research_interests", sa.Text(), nullable=True)
    )
    op.add_column(
        "teachers",
        sa.Column("education", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "teachers",
        sa.Column(
            "publications", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("teachers", "publications")
    op.drop_column("teachers", "education")
    op.drop_column("teachers", "research_interests")
    op.drop_column("courses", "cover_url")
    op.drop_column("courses", "syllabus")
    op.drop_column("courses", "category")
