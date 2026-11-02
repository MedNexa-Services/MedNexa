from datetime import time

from sqlalchemy import String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Hospital(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hospital"

    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    opening_time: Mapped[time]
    closing_time: Mapped[time]
    timezone: Mapped[str] = mapped_column(String(64), server_default="Asia/Kolkata")
    languages: Mapped[list[str]] = mapped_column(JSONB, server_default=text('\'["en", "hi"]\''))
    general_instructions: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
