import uuid

from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class HospitalInfo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hospital_info"

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hospital.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(50))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
