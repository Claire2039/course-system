"""目录浏览的响应模型（课程 / 教学班 / 教师 / 钟点）与分页信封。

纯直接字段的模型用 ``from_attributes``；含跨表派生字段（如教师的 name 来自 User、
教学班的 course/teacher/time_slots 嵌套）的模型在路由里手工构造，避免 from_attributes
无法穿越关系取 user.name 的问题。
"""

from __future__ import annotations

from datetime import time
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, computed_field

from app.models.constants import CourseCategory

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """统一分页信封。"""

    items: list[T]
    total: int
    limit: int
    offset: int


class PeriodDefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_no: int
    start_time: time
    end_time: time


class TimeSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day_of_week: int
    start_period: int
    end_period: int


class CourseRef(BaseModel):
    """教学班里嵌入的课程摘要。"""

    model_config = ConfigDict(from_attributes=True)

    code: str
    title: str
    credits: int
    description: str | None = None


class TeacherRef(BaseModel):
    """教学班里嵌入的教师摘要（name 来自 User）。"""

    id: int  # = user_id，用于跳转教师详情
    name: str
    teacher_no: str
    bio: str | None = None


class PrereqRef(BaseModel):
    code: str
    title: str


class SyllabusItem(BaseModel):
    """教学进度表的一周条目。"""

    week: int
    title: str
    detail: str | None = None


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    credits: int
    department: str
    category: CourseCategory
    cover_url: str | None = None
    description: str | None = None


class CourseDetail(CourseOut):
    syllabus: list[SyllabusItem] = []
    prerequisites: list[PrereqRef] = []


class TeacherOut(BaseModel):
    id: int  # = user_id
    name: str
    teacher_no: str
    department: str
    title: str
    bio: str | None = None
    research_interests: str | None = None


class EducationEntry(BaseModel):
    degree: str
    institution: str
    year: int


class Publication(BaseModel):
    title: str
    venue: str
    year: int


class TeacherDetail(TeacherOut):
    """教师详情页：含教育经历与文献成果（JSONB）。"""

    education: list[EducationEntry] | None = None
    publications: list[Publication] | None = None


class SectionOut(BaseModel):
    id: int
    capacity: int
    seats_taken: int
    room: str
    semester_id: int
    course: CourseRef
    teacher: TeacherRef
    time_slots: list[TimeSlotOut]

    @computed_field
    @property
    def available(self) -> int:
        """剩余座位 = 容量 − 已选。"""
        return self.capacity - self.seats_taken
