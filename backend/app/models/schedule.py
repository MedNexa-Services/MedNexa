import uuid
from datetime import date, time

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Schedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schedule"
    __table_args__ = (
        UniqueConstraint("doctor_id", "date"),
        CheckConstraint(
            "start_time IS NULL OR end_time IS NULL OR end_time > start_time",
            name="window_valid",
        ),
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("doctor.id", ondelete="CASCADE"))
    date: Mapped[date]
    start_time: Mapped[time | None]
    end_time: Mapped[time | None]
    is_available: Mapped[bool] = mapped_column(server_default=text("true"))
    override_reason: Mapped[str | None] = mapped_column(String(200))
