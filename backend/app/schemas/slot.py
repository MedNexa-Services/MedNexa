import uuid
from datetime import date, time

from pydantic import BaseModel


class SlotOut(BaseModel):
    start: time
    end: time


class DoctorSlotOut(BaseModel):
    doctor_id: uuid.UUID
    doctor_name: str
    speciality: str
    department: str
    date: date
    start: time
    end: time
