"""Test setup: a real Postgres database (mednexa_test), migrated with Alembic.

Services commit real transactions and the concurrency tests need several
sessions that see each other's commits, so tests are isolated by truncating
all tables after each test rather than by rolling back a wrapping transaction.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.deps import get_db, require_staff
from app.config import get_settings
from app.main import create_app
from app.models import Base

BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_DB_URL = get_settings().test_database_url


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Rebuild the test schema from migrations once per run (also tests the migration)."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
async def engine(migrated_database: None) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(TEST_DB_URL, pool_size=25, max_overflow=10)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="session")
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def _clean_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def db(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    """HTTP client against the app, with requests using the test database."""
    app = create_app()

    async def _test_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _test_db
    app.dependency_overrides[require_staff] = lambda: {
        "sub": "admin@hospital.com",
        "role": "Hospital Staff",
        "name": "Dr. Admin",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
