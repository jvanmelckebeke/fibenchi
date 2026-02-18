import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.currency import Currency
from app.models.group import Group
from app.services.currency_service import load_cache as load_currency_cache

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Currencies to seed in tests — subunits + common test currencies
_SEED_CURRENCIES = [
    Currency(code="USD", display_code="USD", divisor=1),
    Currency(code="EUR", display_code="EUR", divisor=1),
    Currency(code="GBP", display_code="GBP", divisor=1),
    Currency(code="GBp", display_code="GBP", divisor=100),
    Currency(code="GBX", display_code="GBP", divisor=100),
    Currency(code="ILS", display_code="ILS", divisor=1),
    Currency(code="ILA", display_code="ILS", divisor=100),
    Currency(code="ZAR", display_code="ZAR", divisor=1),
    Currency(code="ZAc", display_code="ZAR", divisor=100),
    Currency(code="KRW", display_code="KRW", divisor=1),
    Currency(code="JPY", display_code="JPY", divisor=1),
    Currency(code="CAD", display_code="CAD", divisor=1),
]


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed the default Watchlist group (mirrors migration 0004) + currencies
    async with TestSession() as session:
        session.add(Group(name="Watchlist", is_default=True, position=0))
        for c in _SEED_CURRENCIES:
            session.add(Currency(code=c.code, display_code=c.display_code, divisor=c.divisor))
        await session.commit()
    # Populate in-memory currency cache
    async with TestSession() as session:
        await load_currency_cache(session)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    async with TestSession() as session:
        yield session


@pytest.fixture
async def client(db):
    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
