from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# A postgres backend never returns the memory it allocated to parse and plan
# a large statement, so a long-lived pooled connection keeps the high-water
# mark of everything it has ever run. Recycling caps how long one bloated
# backend can sit in the pool holding that memory; the statements themselves
# are kept small at the call sites. The idle-in-transaction timeout is the
# other half: a session left mid-transaction pins row versions and blocks
# autovacuum from reclaiming the dead tuples, which is what let the intraday
# churn accumulate instead of being cleaned up.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args={
        "server_settings": {"idle_in_transaction_session_timeout": "300000"},
    }
    if settings.database_url.startswith("postgresql+asyncpg")
    else {},
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session
