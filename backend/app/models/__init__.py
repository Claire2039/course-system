"""统一导入所有模型，确保 ``Base.metadata`` 被完整填充。

Alembic autogenerate 与 ``Base.metadata.create_all`` 都依赖此处的全量导入。
"""

from app.db.base import Base
from app.models.academics import (
    Course,
    CoursePrerequisite,
    PeriodDef,
    Section,
    Semester,
    TimeSlot,
)
from app.models.assignments import Assignment, Grade, Submission
from app.models.constants import EnrollmentStatus, SubmissionStatus, UserRole
from app.models.enrollment import Enrollment
from app.models.notifications import Notification
from app.models.users import Student, Teacher, User

__all__ = [
    "Base",
    "User",
    "Student",
    "Teacher",
    "Semester",
    "PeriodDef",
    "Course",
    "CoursePrerequisite",
    "Section",
    "TimeSlot",
    "Enrollment",
    "Assignment",
    "Submission",
    "Grade",
    "Notification",
    "UserRole",
    "EnrollmentStatus",
    "SubmissionStatus",
]
