"""Agent tests run against a real Postgres database migrated with the backend's
Alembic migrations, with a separate database (mednexa_agent_test) so they can run
alongside the backend suite."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from app.models import Base, Doctor, Hospital
from app.schemas.doctor import DoctorCreate
from app.schemas.hospital import HospitalCreate, HospitalInfoCreate
from app.services import doctor_service, hospital_service
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
TEST_DB_URL = os.environ.get(
    "MEDNEXA_AGENT_TEST_DATABASE_URL",
    "postgresql+asyncpg://mednexa:mednexa@localhost:5434/mednexa_agent_test",
)
IST = ZoneInfo("Asia/Kolkata")


def next_monday() -> date:
    today = date.today()
    return today + timedelta(days=(7 - today.weekday()) % 7 + 7)


MONDAY = next_monday()
# "Now" for tests: early on the Friday before MONDAY, so MONDAY's slots are all free.
NOW = datetime.combine(MONDAY - timedelta(days=3), time(8), IST)
CALLER = "+919876543210"


async def _ensure_database(url: str) -> None:
    parsed = make_url(url)
    admin = await asyncpg.connect(
        user=parsed.username,
        password=parsed.password,
        host=parsed.host,
        port=parsed.port,
        database="postgres",
    )
    try:
        exists = await admin.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", parsed.database
        )
        if not exists:
            await admin.execute(f'CREATE DATABASE "{parsed.database}"')
    finally:
        await admin.close()


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    import asyncio

    asyncio.run(_ensure_database(TEST_DB_URL))
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
async def engine(migrated_database: None) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(TEST_DB_URL, pool_size=10)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="session")
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def _clean_tables(request: pytest.FixtureRequest) -> AsyncIterator[None]:
    yield
    if "engine" not in request.fixturenames:
        return
    engine: AsyncEngine = request.getfixturevalue("engine")
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@dataclass
class Seed:
    hospital: Hospital
    cardiologist: Doctor
    dermatologist: Doctor


@pytest.fixture
async def seed(session_factory: async_sessionmaker[AsyncSession]) -> Seed:
    async with session_factory() as db:
        hospital = await hospital_service.create_hospital(
            db,
            HospitalCreate(
                name="Test City Hospital",
                address="1 MG Road, Jabalpur",
                phone="+917612000000",
                opening_time=time(9),
                closing_time=time(20),
            ),
        )
        await hospital_service.create_info(
            db,
            hospital.id,
            HospitalInfoCreate(category="Parking", question="Is parking available?",
                               answer="Free parking in the basement."),
        )  # fmt: skip
        doctor_fields = {
            "hospital_id": hospital.id,
            "max_daily_appointments": 10,
            "slot_duration_minutes": 30,
            "available_days": [1, 2, 3, 4, 5],
            "slot_start_time": time(9),
            "slot_end_time": time(11),
        }
        cardio = await doctor_service.create_doctor(
            db, DoctorCreate(name="Dr. Anil Sharma", speciality="Cardiologist",
                             department="Cardiology", **doctor_fields)
        )  # fmt: skip
        derm = await doctor_service.create_doctor(
            db, DoctorCreate(name="Dr. Neha Rao", speciality="Dermatologist",
                             department="Dermatology", **doctor_fields)
        )  # fmt: skip
    return Seed(hospital, cardio, derm)
