import uuid
from datetime import date, time

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class ScheduleOverrideIn(BaseModel):
    date: date
    is_available: bool = True
    start_time: time | None = None
    end_time: time | None = None
    override_reason: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _window_valid(self) -> "ScheduleOverrideIn":
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class ScheduleOverrideOut(ORMModel):
    id: uuid.UUID
    doctor_id: uuid.UUID
    date: date
    is_available: bool
    start_time: time | None
    end_time: time | None
    override_reason: str | None
