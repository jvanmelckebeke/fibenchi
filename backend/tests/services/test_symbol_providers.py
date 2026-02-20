"""Tests for the symbol provider registry and Euronext provider."""

import pytest

from app.services.symbol_providers import get_provider, get_available_providers
from app.services.symbol_providers.euronext import _resolve_market, EuronextProvider

pytestmark = pytest.mark.asyncio(loop_scope="function")


# ---------------------------------------------------------------------------
# _resolve_market unit tests
# ---------------------------------------------------------------------------


def test_resolve_amsterdam():
    suffix, key = _resolve_market('"Euronext Amsterdam"')
    assert suffix == ".AS"
    assert key == "amsterdam"


def test_resolve_paris():
    suffix, key = _resolve_market("Euronext Paris")
    assert suffix == ".PA"
    assert key == "paris"


def test_resolve_brussels():
    suffix, key = _resolve_market("Euronext Brussels")
    assert suffix == ".BR"
    assert key == "brussels"


def test_resolve_oslo():
    suffix, key = _resolve_market("Oslo Børs")
    assert suffix == ".OL"
    assert key == "oslo"


def test_resolve_milan():
    suffix, key = _resolve_market("Euronext Milan")
    assert suffix == ".MI"
    assert key == "milan"


def test_resolve_lisbon():
    suffix, key = _resolve_market("Euronext Lisbon")
    assert suffix == ".LS"
    assert key == "lisbon"


def test_resolve_dublin():
    suffix, key = _resolve_market("Euronext Dublin")
    assert suffix == ".IR"
    assert key == "dublin"


def test_resolve_growth_paris():
    suffix, key = _resolve_market("Euronext Growth Paris")
    assert suffix == ".PA"
    assert key == "paris"


def test_resolve_access_brussels():
    suffix, key = _resolve_market("Euronext Access Brussels")
    assert suffix == ".BR"
    assert key == "brussels"


def test_resolve_multi_market_uses_first():
    suffix, key = _resolve_market("Euronext Brussels, Amsterdam")
    assert suffix == ".BR"
    assert key == "brussels"


def test_resolve_skips_global_equity():
    suffix, key = _resolve_market("Euronext Global Equity Market")
    assert suffix is None
    assert key is None


def test_resolve_skips_trading_after_hours():
    suffix, key = _resolve_market("Trading After Hours")
    assert suffix is None
    assert key is None


def test_resolve_skips_eurotlx():
    suffix, key = _resolve_market("EuroTLX")
    assert suffix is None
    assert key is None


def test_resolve_unknown_market():
    suffix, key = _resolve_market("Some Unknown Exchange")
    assert suffix is None
    assert key is None


# ---------------------------------------------------------------------------
# CSV parsing integration test (with mocked HTTP)
# ---------------------------------------------------------------------------

SAMPLE_CSV = """\
\ufeffName;ISIN;Symbol;Market;Currency;"Open Price";"High Price";"low Price";"last Price";"last Trade MIC Time";"Time Zone";Volume;Turnover;"Closing Price";"Closing Price DateTime"
"European Equities"
"20 Feb 2026"
"All datapoints provided as of end of last active trading day."
"AALBERTS NV";NL0000852564;AALB;"Euronext Amsterdam";EUR;42.50;43.00;42.00;42.80;"19/02/2026 16:25";CET;100000;4280000.00;42.80;19/02/2026
"AB INBEV";BE0974293251;ABI;"Euronext Brussels";EUR;55.00;55.50;54.80;55.20;"19/02/2026 16:30";CET;200000;11040000.00;55.20;19/02/2026
ACCOR;FR0000120404;AC;"Euronext Paris";EUR;38.10;38.50;37.90;38.30;"19/02/2026 16:35";CET;150000;5745000.00;38.30;19/02/2026
"DNB BANK";NO0010031479;DNB;"Oslo Børs";NOK;220.00;221.50;219.00;220.80;"19/02/2026 16:25";CET;80000;17664000.00;220.80;19/02/2026
"ZOOM COMMUNICATION";US98980L1017;2ZM;"Trading After Hours";EUR;76.03;76.03;76.03;76.03;"12/02/2026 19:58";CET;160;12164.80;78.43;19/02/2026
"CROSS LISTED";XX1234567890;XLIST;"Euronext Brussels, Amsterdam";EUR;10.00;10.50;9.80;10.20;"19/02/2026 16:00";CET;5000;51000.00;10.20;19/02/2026
"GLOBAL STOCK";US0000000001;GLOB;"Euronext Global Equity Market";EUR;100.00;101.00;99.00;100.50;"19/02/2026 16:00";CET;1000;100500.00;100.50;19/02/2026
"GROWTH PARIS CO";FR9999999999;GPC;"Euronext Growth Paris";EUR;5.00;5.10;4.90;5.05;"19/02/2026 16:00";CET;3000;15150.00;5.05;19/02/2026
"""


async def test_euronext_provider_parses_csv(monkeypatch):
    """Test full CSV parsing with mocked HTTP response."""

    class MockResponse:
        status_code = 200
        text = SAMPLE_CSV

        def raise_for_status(self):
            pass

    class MockClient:
        async def get(self, url):
            return MockResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: MockClient())

    provider = EuronextProvider()
    results = await provider.fetch_symbols({"markets": []})

    symbols = {r.symbol for r in results}
    assert "AALB.AS" in symbols  # Amsterdam
    assert "ABI.BR" in symbols  # Brussels
    assert "AC.PA" in symbols  # Paris
    assert "DNB.OL" in symbols  # Oslo
    assert "XLIST.BR" in symbols  # Multi-market → first market (Brussels)
    assert "GPC.PA" in symbols  # Growth Paris → .PA

    # Skipped markets
    assert "2ZM" not in symbols and not any("2ZM" in s for s in symbols)  # Trading After Hours
    assert "GLOB" not in symbols and not any("GLOB" in s for s in symbols)  # Global Equity Market


async def test_euronext_provider_filters_by_market(monkeypatch):
    """Test that market filter restricts results."""

    class MockResponse:
        status_code = 200
        text = SAMPLE_CSV

        def raise_for_status(self):
            pass

    class MockClient:
        async def get(self, url):
            return MockResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: MockClient())

    provider = EuronextProvider()
    results = await provider.fetch_symbols({"markets": ["amsterdam"]})

    symbols = {r.symbol for r in results}
    assert "AALB.AS" in symbols
    assert "ABI.BR" not in symbols  # Brussels filtered out
    assert "AC.PA" not in symbols  # Paris filtered out


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


def test_get_provider_euronext():
    provider = get_provider("euronext")
    assert isinstance(provider, EuronextProvider)


def test_get_provider_unknown():
    with pytest.raises(ValueError, match="Unknown provider type"):
        get_provider("nonexistent")


def test_get_available_providers():
    providers = get_available_providers()
    assert "euronext" in providers
    assert len(providers["euronext"]["markets"]) >= 7
    assert providers["euronext"]["markets"][0]["key"] == "amsterdam"
