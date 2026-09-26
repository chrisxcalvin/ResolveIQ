from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# Neon (serverless Postgres behind a pooler) closes idle connections and
# scales compute to zero when quiet. Without pre-ping, SQLAlchemy hands out
# a pooled connection that is already dead and the first query after any
# quiet period fails with "connection was closed in the middle of
# operation" - seen both as a 500 on the first API request after idle and
# as a lost Celery task (docs/checkpoints/phase-7.md). pool_pre_ping
# validates a connection at checkout and transparently reconnects;
# pool_recycle retires connections before Neon's ~5 min idle cutoff would
# kill them anyway.
engine = create_async_engine(
    settings.database_url, echo=False, pool_pre_ping=True, pool_recycle=240
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
