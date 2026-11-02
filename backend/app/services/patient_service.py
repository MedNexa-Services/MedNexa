import uuid
from difflib import SequenceMatcher

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound
from app.core.normalize import normalize_name
from app.models import Patient
from app.schemas.patient import PatientCreate, PatientIn, PatientUpdate
from app.services.common import apply_updates, paginate
from app.services.hospital_service import get_hospital


async def find_patient(
    db: AsyncSession, hospital_id: uuid.UUID, phone: str, name: str
) -> Patient | None:
    return await db.scalar(
        select(Patient).where(
            Patient.hospital_id == hospital_id,
            Patient.phone == phone,
            Patient.normalized_name == normalize_name(name),
        )
    )


_CLOSE_ENOUGH = 0.8


def _letters(name: str) -> str:
    return "".join(ch for ch in normalize_name(name) if ch.isalpha() or ch == " ")


def _closeness(heard: str, stored: str) -> float:
    heard, stored = _letters(heard), _letters(stored)
    best = SequenceMatcher(None, heard, stored).ratio()
    if " " not in heard:
        best = max(best, *(SequenceMatcher(None, heard, part).ratio() for part in stored.split()))
    return best


async def find_patient_by_sound(
    db: AsyncSession, hospital_id: uuid.UUID, phone: str, name: str
) -> Patient | None:
    patients = await db.scalars(
        select(Patient).where(Patient.hospital_id == hospital_id, Patient.phone == phone)
    )
    scored = sorted(
        ((_closeness(name, p.name), p) for p in patients), key=lambda x: x[0], reverse=True
    )
    close = [(score, p) for score, p in scored if score >= _CLOSE_ENOUGH]
    if len(close) == 1 or (len(close) > 1 and close[0][0] - close[1][0] >= 0.1):
        return close[0][1]
    return None


async def upsert_patient(db: AsyncSession, hospital_id: uuid.UUID, data: PatientIn) -> Patient:
    values = insert(Patient).values(
        hospital_id=hospital_id,
        name=data.name,
        normalized_name=normalize_name(data.name),
        phone=data.phone,
        age=data.age,
        gender=data.gender,
        email=data.email,
        address=data.address,
    )
    excluded = values.excluded
    stmt = values.on_conflict_do_update(
        constraint="uq_patient_hospital_id_phone_normalized_name",
        set_={
            "age": func.coalesce(excluded.age, Patient.age),
            "gender": func.coalesce(excluded.gender, Patient.gender),
            "email": func.coalesce(excluded.email, Patient.email),
            "address": func.coalesce(excluded.address, Patient.address),
            "updated_at": func.now(),
        },
    ).returning(Patient)
    patient: Patient = (await db.scalars(stmt, execution_options={"populate_existing": True})).one()
    return patient


async def get_patient(db: AsyncSession, patient_id: uuid.UUID) -> Patient:
    patient = await db.get(Patient, patient_id)
    if patient is None:
        raise NotFound("Patient not found")
    return patient


async def create_patient(db: AsyncSession, data: PatientCreate) -> Patient:
    await get_hospital(db, data.hospital_id)
    if await find_patient(db, data.hospital_id, data.phone, data.name):
        raise Conflict("A patient with this phone number and name already exists")
    patient = Patient(
        **data.model_dump(exclude={"name"}),
        name=data.name,
        normalized_name=normalize_name(data.name),
    )
    db.add(patient)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise Conflict("A patient with this phone number and name already exists") from exc
    await db.refresh(patient)
    return patient


async def search_patients(
    db: AsyncSession,
    *,
    hospital_id: uuid.UUID | None = None,
    phone: str | None = None,
    name: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Patient], int]:
    stmt = select(Patient)
    if hospital_id:
        stmt = stmt.where(Patient.hospital_id == hospital_id)
    if phone:
        stmt = stmt.where(Patient.phone == phone)
    if name:
        stmt = stmt.where(Patient.normalized_name.contains(normalize_name(name), autoescape=True))
    return await paginate(db, stmt.order_by(Patient.name), limit, offset)


async def update_patient(db: AsyncSession, patient_id: uuid.UUID, data: PatientUpdate) -> Patient:
    patient = await get_patient(db, patient_id)
    apply_updates(patient, data.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(patient)
    return patient
