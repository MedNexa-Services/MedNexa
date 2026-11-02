import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus, BookingSource
from app.models.patient import Patient


class Appointment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "appointment"
    __table_args__ = (
        Index(
            "uq_appointment_doctor_slot_booked",
            "doctor_id",
            "appointment_date",
            "appointment_time",
            unique=True,
            postgresql_where=text("status = 'BOOKED'"),
        ),
        UniqueConstraint("doctor_id", "appointment_date", "token_number"),
        Index("ix_appointment_doctor_date", "doctor_id", "appointment_date"),
        Index("ix_appointment_hospital_date", "hospital_id", "appointment_date"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patient.id", ondelete="RESTRICT"), index=True
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("doctor.id", ondelete="RESTRICT"))
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospital.id", ondelete="RESTRICT"))
    appointment_date: Mapped[date]
    appointment_time: Mapped[time]
    slot_duration_minutes: Mapped[int]
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status"),
        server_default=AppointmentStatus.BOOKED.value,
    )
    booking_source: Mapped[BookingSource] = mapped_column(
        Enum(BookingSource, name="booking_source")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    token_number: Mapped[int]
    rescheduled_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("appointment.id", ondelete="SET NULL")
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))

    patient: Mapped[Patient] = relationship(lazy="raise")
    doctor: Mapped[Doctor] = relationship(lazy="raise")
