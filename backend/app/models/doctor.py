import uuid
from datetime import time

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.hospital import Hospital


class Doctor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "doctor"
    __table_args__ = (
        CheckConstraint("slot_duration_minutes > 0", name="slot_duration_positive"),
        CheckConstraint("max_daily_appointments > 0", name="max_daily_positive"),
        CheckConstraint("slot_end_time > slot_start_time", name="slot_window_valid"),
        Index("ix_doctor_hospital_speciality", "hospital_id", "speciality"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospital.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    speciality: Mapped[str] = mapped_column(String(100))
    qualification: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(100))
    max_daily_appointments: Mapped[int]
    slot_duration_minutes: Mapped[int]
    available_days: Mapped[list[int]] = mapped_column(JSONB)
    slot_start_time: Mapped[time]
    slot_end_time: Mapped[time]
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    bio: Mapped[str | None] = mapped_column(Text)

    hospital: Mapped[Hospital] = relationship(lazy="raise")
