import uuid
from datetime import datetime, time

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel, reject_explicit_nulls
from app.schemas.schedule import ScheduleOverrideOut


def _clean_days(days: list[int]) -> list[int]:
    if any(d < 1 or d > 7 for d in days):
        raise ValueError("available_days must be ISO weekdays 1 (Mon) .. 7 (Sun)")
    return sorted(set(days))


class DoctorCreate(BaseModel):
    hospital_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    speciality: str = Field(min_length=1, max_length=100)
    qualification: str | None = Field(default=None, max_length=200)
    department: str = Field(min_length=1, max_length=100)
    max_daily_appointments: int = Field(gt=0, le=500)
    slot_duration_minutes: int = Field(gt=0, le=480)
    available_days: list[int] = Field(min_length=1)
    slot_start_time: time
    slot_end_time: time
    bio: str | None = None

    _days = field_validator("available_days")(_clean_days)

    @model_validator(mode="after")
    def _window_valid(self) -> "DoctorCreate":
        if self.slot_end_time <= self.slot_start_time:
            raise ValueError("slot_end_time must be after slot_start_time")
        return self


class DoctorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    speciality: str | None = Field(default=None, min_length=1, max_length=100)
    qualification: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, min_length=1, max_length=100)
    max_daily_appointments: int | None = Field(default=None, gt=0, le=500)
    slot_duration_minutes: int | None = Field(default=None, gt=0, le=480)
    available_days: list[int] | None = Field(default=None, min_length=1)
    slot_start_time: time | None = None
    slot_end_time: time | None = None
    is_active: bool | None = None
    bio: str | None = None

    @field_validator("available_days")
    @classmethod
    def _days(cls, days: list[int] | None) -> list[int] | None:
        return None if days is None else _clean_days(days)

    @model_validator(mode="after")
    def _no_nulls(self) -> "DoctorUpdate":
        reject_explicit_nulls(self, nullable=frozenset({"qualification", "bio"}))
        return self


class DoctorOut(ORMModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    name: str
    speciality: str
    qualification: str | None
    department: str
    max_daily_appointments: int
    slot_duration_minutes: int
    available_days: list[int]
    slot_start_time: time
    slot_end_time: time
    is_active: bool
    bio: str | None
    created_at: datetime
    updated_at: datetime


class DoctorDetailOut(DoctorOut):
    upcoming_overrides: list[ScheduleOverrideOut]
