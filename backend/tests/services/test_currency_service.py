"""Tests for the currency lookup service (cache + DB integration)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.currency import Currency
from app.services.currency_service import _cache, load_cache, lookup, ensure_currency

pytestmark = pytest.mark.asyncio(loop_scope="function")


# ---------------------------------------------------------------------------
# lookup (pure in-memory, relies on cache populated by conftest setup_db)
# ---------------------------------------------------------------------------


def test_lookup_known_currency():
    """Known currencies return their display code and divisor."""
    display, divisor = lookup("USD")
    assert display == "USD"
    assert divisor == 1


def test_lookup_subunit_gbp():
    """Subunit GBp maps to GBP with divisor 100."""
    display, divisor = lookup("GBp")
    assert display == "GBP"
    assert divisor == 100


def test_lookup_subunit_gbx():
    """Subunit GBX maps to GBP with divisor 100."""
    display, divisor = lookup("GBX")
    assert display == "GBP"
    assert divisor == 100


def test_lookup_subunit_ila():
    """Subunit ILA maps to ILS with divisor 100."""
    display, divisor = lookup("ILA")
    assert display == "ILS"
    assert divisor == 100


def test_lookup_subunit_zac():
    """Subunit ZAc maps to ZAR with divisor 100."""
    display, divisor = lookup("ZAc")
    assert display == "ZAR"
    assert divisor == 100


def test_lookup_unknown_falls_back():
    """Unknown codes fall back to (raw_code, 1)."""
    display, divisor = lookup("UNKNOWN_XYZ")
    assert display == "UNKNOWN_XYZ"
    assert divisor == 1


# ---------------------------------------------------------------------------
# load_cache (async, uses the test DB seeded by conftest)
# ---------------------------------------------------------------------------


async def test_load_cache_populates(db):
    """load_cache fills the module-level cache from the DB."""
    _cache.clear()
    assert len(_cache) == 0

    await load_cache(db)

    assert len(_cache) > 0
    # Seeded currencies should be present
    assert "USD" in _cache
    assert "GBp" in _cache


async def test_load_cache_includes_subunit_safety_net(db):
    """Even if DB is missing subunit entries, safety net fills them in."""
    # Clear the DB currencies and reload
    from sqlalchemy import delete
    await db.execute(delete(Currency))
    await db.commit()

    await load_cache(db)

    # Subunit safety net should still be present
    assert _cache.get("GBp") == ("GBP", 100)
    assert _cache.get("GBX") == ("GBP", 100)
    assert _cache.get("ILA") == ("ILS", 100)
    assert _cache.get("ZAc") == ("ZAR", 100)


# ---------------------------------------------------------------------------
# ensure_currency (async, auto-registers unknown codes)
# ---------------------------------------------------------------------------


async def test_ensure_currency_noop_for_known(db):
    """ensure_currency is a no-op when the code is already in the cache."""
    cache_size_before = len(_cache)
    await ensure_currency(db, "USD")
    assert len(_cache) == cache_size_before


async def test_ensure_currency_registers_unknown(db):
    """ensure_currency inserts a new code into DB and cache."""
    assert "NEW_CODE" not in _cache

    await ensure_currency(db, "NEW_CODE")

    assert "NEW_CODE" in _cache
    assert _cache["NEW_CODE"] == ("NEW_CODE", 1)

    # Verify it was persisted to the DB
    from sqlalchemy import select
    result = await db.execute(select(Currency).where(Currency.code == "NEW_CODE"))
    row = result.scalar_one()
    assert row.display_code == "NEW_CODE"
    assert row.divisor == 1
