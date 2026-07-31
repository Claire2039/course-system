"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-29

Creates all 14 tables (see SPEC sec 3.2). Constraint/index names follow the
naming convention in app/models so later `alembic revision --autogenerate`
produces no naming churn.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.constants import EnrollmentStatus, SubmissionStatus, UserRole

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                UserRole,
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # --- students (1-1 to users) ---
    op.create_table(
        "students",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("student_no", sa.String(length=32), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("major", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_students_user_id_users"
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_students"),
        sa.UniqueConstraint("student_no", name="uq_students_student_no"),
    )

    # --- teachers (1-1 to users) ---
    op.create_table(
        "teachers",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_no", sa.String(length=32), nullable=False),
        sa.Column("department", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_teachers_user_id_users"
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_teachers"),
        sa.UniqueConstraint("teacher_no", name="uq_teachers_teacher_no"),
    )

    # --- semesters ---
    op.create_table(
        "semesters",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("enroll_open_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enroll_close_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("drop_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_credits", sa.Integer(), nullable=False),
        sa.Column("max_courses", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_semesters"),
    )

    # --- period_defs ---
    op.create_table(
        "period_defs",
        sa.Column("period_no", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.PrimaryKeyConstraint("period_no", name="pk_period_defs"),
    )

    # --- courses ---
    op.create_table(
        "courses",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("credits", sa.SmallInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("department", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_courses"),
        sa.UniqueConstraint("code", name="uq_courses_code"),
    )

    # --- course_prerequisites (composite PK, self-referential M:N) ---
    op.create_table(
        "course_prerequisites",
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("prereq_course_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name="fk_course_prerequisites_course_id_courses"
        ),
        sa.ForeignKeyConstraint(
            ["prereq_course_id"],
            ["courses.id"],
            name="fk_course_prerequisites_prereq_course_id_courses",
        ),
        sa.PrimaryKeyConstraint(
            "course_id", "prereq_course_id", name="pk_course_prerequisites"
        ),
    )

    # --- sections ---
    op.create_table(
        "sections",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_id", sa.BigInteger(), nullable=False),
        sa.Column("semester_id", sa.BigInteger(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column(
            "seats_taken", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("room", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("capacity > 0", name="sections_capacity_positive"),
        sa.CheckConstraint("seats_taken >= 0", name="sections_seats_taken_nonneg"),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name="fk_sections_course_id_courses"
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"], ["teachers.user_id"], name="fk_sections_teacher_id_teachers"
        ),
        sa.ForeignKeyConstraint(
            ["semester_id"], ["semesters.id"], name="fk_sections_semester_id_semesters"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sections"),
    )
    op.create_index("ix_sections_course_id", "sections", ["course_id"], unique=False)
    op.create_index("ix_sections_teacher_id", "sections", ["teacher_id"], unique=False)
    op.create_index(
        "ix_sections_semester_id", "sections", ["semester_id"], unique=False
    )

    # --- time_slots ---
    op.create_table(
        "time_slots",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("section_id", sa.BigInteger(), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("start_period", sa.SmallInteger(), nullable=False),
        sa.Column("end_period", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "day_of_week BETWEEN 1 AND 7", name="time_slots_day_of_week_range"
        ),
        sa.CheckConstraint(
            "start_period <= end_period", name="time_slots_period_order"
        ),
        sa.ForeignKeyConstraint(
            ["section_id"], ["sections.id"], name="fk_time_slots_section_id_sections"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_time_slots"),
    )
    op.create_index("ix_time_slots_section_id", "time_slots", ["section_id"], unique=False)

    # --- enrollments ---
    op.create_table(
        "enrollments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("section_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                EnrollmentStatus,
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("waitlist_position", sa.Integer(), nullable=True),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.user_id"], name="fk_enrollments_student_id_students"
        ),
        sa.ForeignKeyConstraint(
            ["section_id"], ["sections.id"], name="fk_enrollments_section_id_sections"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_enrollments"),
        sa.UniqueConstraint(
            "student_id", "section_id", name="enrollments_student_section_unique"
        ),
    )
    op.create_index(
        "ix_enrollments_section_status", "enrollments", ["section_id", "status"], unique=False
    )
    op.create_index(
        "ix_enrollments_student_status", "enrollments", ["student_id", "status"], unique=False
    )

    # --- assignments ---
    op.create_table(
        "assignments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("section_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("late_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "allow_late",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("attachment_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["section_id"], ["sections.id"], name="fk_assignments_section_id_sections"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assignments"),
    )
    op.create_index(
        "ix_assignments_section_id", "assignments", ["section_id"], unique=False
    )

    # --- submissions ---
    op.create_table(
        "submissions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("assignment_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("file_key", sa.String(length=255), nullable=True),
        sa.Column("text_comment", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                SubmissionStatus,
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignments.id"],
            name="fk_submissions_assignment_id_assignments",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.user_id"], name="fk_submissions_student_id_students"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_submissions"),
        sa.UniqueConstraint(
            "assignment_id", "student_id", name="submissions_assignment_student_unique"
        ),
    )
    op.create_index(
        "ix_submissions_assignment_id",
        "submissions",
        ["assignment_id"],
        unique=False,
    )
    op.create_index(
        "ix_submissions_student_id", "submissions", ["student_id"], unique=False
    )

    # --- grades (1-1 to submissions) ---
    op.create_table(
        "grades",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("submission_id", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column(
            "graded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("graded_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["submissions.id"],
            name="fk_grades_submission_id_submissions",
        ),
        sa.ForeignKeyConstraint(
            ["graded_by"], ["users.id"], name="fk_grades_graded_by_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_grades"),
        sa.UniqueConstraint("submission_id", name="uq_grades_submission_id"),
    )
    op.create_index("ix_grades_graded_by", "grades", ["graded_by"], unique=False)

    # --- notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "read",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_notifications_user_id_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("grades")
    op.drop_table("submissions")
    op.drop_table("assignments")
    op.drop_table("enrollments")
    op.drop_table("time_slots")
    op.drop_table("sections")
    op.drop_table("course_prerequisites")
    op.drop_table("courses")
    op.drop_table("period_defs")
    op.drop_table("semesters")
    op.drop_table("teachers")
    op.drop_table("students")
    op.drop_table("users")
