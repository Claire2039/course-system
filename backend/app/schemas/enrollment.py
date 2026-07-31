"""选课/候补相关的响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.constants import EnrollmentStatus
from app.schemas.catalog import TimeSlotOut


class CourseBrief(BaseModel):
    code: str
    title: str


class EnrollmentSection(BaseModel):
    id: int
    course: CourseBrief
    time_slots: list[TimeSlotOut] = []


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    section_id: int
    status: EnrollmentStatus
    waitlist_position: int | None = None
    section: EnrollmentSection


class EnrollResponse(BaseModel):
    status: EnrollmentStatus  # ENROLLED | WAITLISTED
    enrollment_id: int
    position: int | None = None  # 候补位次（ENROLLED 时为 None）
