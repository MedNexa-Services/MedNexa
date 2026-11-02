import uuid

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Gender


class Patient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patient"
    __table_args__ = (
        UniqueConstraint("hospital_id", "phone", "normalized_name"),
        CheckConstraint("age IS NULL OR (age >= 0 AND age <= 150)", name="age_range"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospital.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    age: Mapped[int | None]
    gender: Mapped[Gender | None] = mapped_column(Enum(Gender, name="gender"))
    email: Mapped[str | None] = mapped_column(String(254))
    address: Mapped[str | None] = mapped_column(Text)
