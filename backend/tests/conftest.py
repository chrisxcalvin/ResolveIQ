"""Shared fixtures for the DB-backed and HTTP-level tests.

Uses a disposable `resolveiq_test` database (same WSL2 Postgres instance,
pgvector enabled) rather than SQLite, since several models use a real
`vector` column that SQLite can't represent. Each test runs inside its own
outer transaction that's rolled back afterward — including when the code
under test calls `db.commit()` itself (e.g. resolve_ticket), which is what
`join_transaction_mode="create_savepoint"` is for: an internal commit only
releases a SAVEPOINT, the outer transaction survives and gets rolled back
by this fixture, so tests never leave rows behind or touch the real dev DB.
"""

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.security import create_access_token, hash_password
from app.db.base import Base, get_db
from app.main import app
from app.models.user import User

TEST_DATABASE_URL = "postgresql+asyncpg://resolveiq:resolveiq_dev_password@localhost:5432/resolveiq_test"

_test_engine = create_async_engine(TEST_DATABASE_URL)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session():
    async with _test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def agent_user(db_session):
    user = User(
        email=f"agent-{uuid.uuid4().hex[:8]}@test.local",
        password_hash=hash_password("testpass123"),
        role="agent",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
def auth_headers(agent_user):
    token = create_access_token(agent_user.id, agent_user.role)
    return {"Authorization": f"Bearer {token}"}
