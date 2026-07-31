"""领域枚举。

以 Python ``StrEnum`` 表达；存库为 ``VARCHAR`` + ``CHECK``（见各模型列声明与
``Enum(native_enum=False, create_constraint=True)``）。值与 SPEC 记号一致（大写），
且 ``name == value``，可直接 JSON 序列化、亦方便肉眼读库。
"""

from enum import StrEnum


class UserRole(StrEnum):
    STUDENT = "STUDENT"
    TEACHER = "TEACHER"
    ADMIN = "ADMIN"


class EnrollmentStatus(StrEnum):
    ENROLLED = "ENROLLED"
    WAITLISTED = "WAITLISTED"
    DROPPED = "DROPPED"


class SubmissionStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    LATE = "LATE"
