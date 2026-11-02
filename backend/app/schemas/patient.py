import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Gender
from app.schemas.common import ORMModel, PersonName, Phone


class PatientIn(BaseModel):
    name: PersonName
    phone: Phone
    age: int | None = Field(default=None, ge=0, le=150)
    gender: Gender | None = None
    email: EmailStr | None = None
    address: str | None = None


class PatientCreate(PatientIn):
    hospital_id: uuid.UUID


class PatientUpdate(BaseModel):
    age: int | None = Field(default=None, ge=0, le=150)
    gender: Gender | None = None
    email: EmailStr | None = None
    address: str | None = None


class PatientOut(ORMModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    name: str
    phone: str
    age: int | None
    gender: Gender | None
    email: str | None
    address: str | None
    created_at: datetime
    updated_at: datetime
