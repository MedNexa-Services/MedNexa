import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field

from app.models import Appointment
from app.models.enums import AppointmentStatus, BookingSource
from app.schemas.patient import PatientIn


class BookingRequest(BaseModel):
    patient: PatientIn
    doctor_id: uuid.UUID
    appointment_date: date
    appointment_time: time
    notes: str | None = None
    booking_source: BookingSource = BookingSource.AI_CALL


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class RescheduleRequest(BaseModel):
    new_date: date
    new_time: time


class AppointmentOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    patient_phone: str
    doctor_id: uuid.UUID
    doctor_name: str
    department: str
    hospital_id: uuid.UUID
    appointment_date: date
    appointment_time: time
    slot_duration_minutes: int
    status: AppointmentStatus
    booking_source: BookingSource
    token_number: int
    notes: str | None
    rescheduled_from_id: uuid.UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, appt: Appointment) -> "AppointmentOut":
        return cls(
            id=appt.id,
            patient_id=appt.patient_id,
            patient_name=appt.patient.name,
            patient_phone=appt.patient.phone,
            doctor_id=appt.doctor_id,
            doctor_name=appt.doctor.name,
            department=appt.doctor.department,
            hospital_id=appt.hospital_id,
            appointment_date=appt.appointment_date,
            appointment_time=appt.appointment_time,
            slot_duration_minutes=appt.slot_duration_minutes,
            status=appt.status,
            booking_source=appt.booking_source,
            token_number=appt.token_number,
            notes=appt.notes,
            rescheduled_from_id=appt.rescheduled_from_id,
            cancelled_at=appt.cancelled_at,
            cancellation_reason=appt.cancellation_reason,
            created_at=appt.created_at,
        )


class BookingConfirmation(BaseModel):
    appointment_id: uuid.UUID
    token_number: int
    patient_name: str
    doctor_name: str
    department: str
    appointment_date: date
    appointment_time: time
    status: AppointmentStatus

    @classmethod
    def from_model(cls, appt: Appointment) -> "BookingConfirmation":
        return cls(
            appointment_id=appt.id,
            token_number=appt.token_number,
            patient_name=appt.patient.name,
            doctor_name=appt.doctor.name,
            department=appt.doctor.department,
            appointment_date=appt.appointment_date,
            appointment_time=appt.appointment_time,
            status=appt.status,
        )
