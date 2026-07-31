"""教师工作台响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.catalog import CourseRef


class MySectionOut(BaseModel):
    """我教的教学班。"""

    id: int
    course: CourseRef
    semester_id: int
    capacity: int
    seats_taken: int
    enrolled_count: int


class RosterStudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    name: str
    student_no: str
