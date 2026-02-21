"""Tests for the symbol provider registry and individual providers."""

import pytest

from app.services.symbol_providers import get_provider, get_available_providers
from app.services.symbol_providers.euronext import _resolve_market, EuronextProvider
from app.services.symbol_providers.xetra import XetraProvider

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

SAMPLE_STOCKS_CSV = """\
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

SAMPLE_ETFS_CSV = """\
\ufeffName;ISIN;Symbol;Market;Currency;"Open Price";"High Price";"low Price";"last Price";"last Trade MIC Time";"Time Zone";Volume;Turnover;"Closing Price";"Closing Price DateTime"
"European ETFS, Funds, ETVs, ETNs. Type : ETFs"
"20 Feb 2026"
"All datapoints provided as of end of last active trading day."
"ISHARES MSCI WOR A";IE00B4L5Y983;IWDA;"Euronext Amsterdam";EUR;113.515;113.63;112.925;113.385;"19/02/2026 17:38";CET;47814;5417502.86;113.385;19/02/2026
"ISHARES EMIM";IE00BKM4GZ66;EMIM;"Euronext Amsterdam";EUR;42.699;42.699;42.336;42.546;"19/02/2026 17:35";CET;71784;3052652.58;42.546;19/02/2026
"AM ASIP EXJ PEA";FR0011869312;PAEJ;"Euronext Paris";EUR;24.219;24.219;23.874;24.009;"19/02/2026 17:35";CET;12302;295691.36;24.009;19/02/2026
"""


def _make_mock_client(stocks_csv, etfs_csv):
    """Create a mock httpx.AsyncClient that returns different CSVs per URL."""
    from app.services.symbol_providers.euronext import EURONEXT_STOCKS_URL, EURONEXT_ETFS_URL

    class MockResponse:
        def __init__(self, text):
            self.text = text
            self.status_code = 200
        def raise_for_status(self):
            pass

    class MockClient:
        async def get(self, url):
            if "track" in url:
                return MockResponse(etfs_csv)
            return MockResponse(stocks_csv)
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    return MockClient


async def test_euronext_provider_parses_csv(monkeypatch):
    """Test full CSV parsing with mocked HTTP response."""
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _make_mock_client(SAMPLE_STOCKS_CSV, SAMPLE_ETFS_CSV)())

    provider = EuronextProvider()
    results = await provider.fetch_symbols({"markets": []})

    symbols = {r.symbol for r in results}
    assert "AALB.AS" in symbols  # Amsterdam stock
    assert "ABI.BR" in symbols  # Brussels stock
    assert "AC.PA" in symbols  # Paris stock
    assert "DNB.OL" in symbols  # Oslo stock
    assert "XLIST.BR" in symbols  # Multi-market → first market (Brussels)
    assert "GPC.PA" in symbols  # Growth Paris → .PA

    # ETFs
    assert "IWDA.AS" in symbols  # Amsterdam ETF
    assert "EMIM.AS" in symbols  # Amsterdam ETF
    assert "PAEJ.PA" in symbols  # Paris ETF

    # Type checks
    by_symbol = {r.symbol: r for r in results}
    assert by_symbol["AALB.AS"].type == "stock"
    assert by_symbol["IWDA.AS"].type == "etf"
    assert by_symbol["EMIM.AS"].type == "etf"

    # Skipped markets
    assert "2ZM" not in symbols and not any("2ZM" in s for s in symbols)  # Trading After Hours
    assert "GLOB" not in symbols and not any("GLOB" in s for s in symbols)  # Global Equity Market


async def test_euronext_provider_filters_by_market(monkeypatch):
    """Test that market filter restricts results."""
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _make_mock_client(SAMPLE_STOCKS_CSV, SAMPLE_ETFS_CSV)())

    provider = EuronextProvider()
    results = await provider.fetch_symbols({"markets": ["amsterdam"]})

    symbols = {r.symbol for r in results}
    assert "AALB.AS" in symbols  # Amsterdam stock
    assert "IWDA.AS" in symbols  # Amsterdam ETF
    assert "ABI.BR" not in symbols  # Brussels filtered out
    assert "AC.PA" not in symbols  # Paris filtered out
    assert "PAEJ.PA" not in symbols  # Paris ETF filtered out


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
    assert "xetra" in providers
    assert providers["xetra"]["markets"][0]["key"] == "xetra"


# ---------------------------------------------------------------------------
# Xetra provider tests
# ---------------------------------------------------------------------------

SAMPLE_XETRA_CSV = """\
Market:;XETR
Date Last Update:;20.02.2026
Product Status;Instrument Status;Instrument;ISIN;Product ID;Instrument ID;WKN;Mnemonic;MIC Code;CCP eligible Code;Trading Model Type;Product Assignment Group;Product Assignment Group Description;Designated Sponsor Member ID;Designated Sponsor;Price Range Value;Price Range Percentage;Minimum Quote Size;Instrument Type;Currency
Active;Active;SIEMENS AG NA O.N.;DE0007236101;40001;2504193;723610;SIE;XETR;Y;Continuous;DAX0;DAX;BALFR;BAADER BANK AG;;2;111;CS;EUR
Active;Active;ISHARES CORE DAX;DE0005933931;40002;2504194;593393;EXS1;XETR;Y;Continuous;FON1;EXCHANGE TRADED FUNDS;LSTDU;LANG & SCHWARZ;;6;53400;ETF;EUR
Active;Active;21SHARES BITCOIN ETP;CH0454664001;40003;2504195;A2T64E;2BTC;XETR;Y;Continuous;ETN0;EXCHANGE TRADED NOTES;BALFR;BAADER BANK;;5;2600;ETN;EUR
Active;Active;SAP SE O.N.;DE0007164600;40004;2504196;716460;SAP;XETR;Y;Continuous;DAX0;DAX;BALFR;BAADER BANK AG;;2;111;CS;EUR
Inactive;Active;DELISTED AG;DE9999999999;40005;2504197;999999;DEL;XETR;Y;Continuous;AST0;GENERAL STANDARD;BALFR;BAADER BANK;;2;111;CS;EUR
Active;Inactive;SUSPENDED AG;DE8888888888;40006;2504198;888888;SUS;XETR;Y;Continuous;AST0;GENERAL STANDARD;BALFR;BAADER BANK;;2;111;CS;EUR
Active;Active;XETRA GOLD;DE000A0S9GB0;40007;2504199;A0S9GB;4GLD;XETR;Y;Continuous;ETC0;EXCHANGE TRADED COMMODITIES;BALFR;BAADER BANK;;5;2600;ETC;EUR
"""


def _make_xetra_mock_client(csv_text):
    """Create a mock httpx.AsyncClient that returns the given CSV."""

    class MockResponse:
        def __init__(self, text):
            self.text = text
            self.status_code = 200
        def raise_for_status(self):
            pass

    class MockClient:
        async def get(self, url):
            return MockResponse(csv_text)
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    return MockClient


async def test_xetra_provider_parses_csv(monkeypatch):
    """Test full CSV parsing with mocked HTTP response."""
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _make_xetra_mock_client(SAMPLE_XETRA_CSV)())

    provider = XetraProvider()
    results = await provider.fetch_symbols({})

    symbols = {r.symbol for r in results}
    assert "SIE.DE" in symbols  # Siemens stock
    assert "SAP.DE" in symbols  # SAP stock
    assert "EXS1.DE" in symbols  # iShares Core DAX ETF

    # Type checks
    by_symbol = {r.symbol: r for r in results}
    assert by_symbol["SIE.DE"].type == "stock"
    assert by_symbol["SAP.DE"].type == "stock"
    assert by_symbol["EXS1.DE"].type == "etf"
    assert by_symbol["SIE.DE"].exchange == "Xetra"
    assert by_symbol["SIE.DE"].currency == "EUR"

    # Filtered out: ETN, ETC, inactive products
    assert "2BTC.DE" not in symbols  # ETN
    assert "4GLD.DE" not in symbols  # ETC
    assert "DEL.DE" not in symbols  # Inactive product
    assert "SUS.DE" not in symbols  # Inactive instrument


def test_get_provider_xetra():
    provider = get_provider("xetra")
    assert isinstance(provider, XetraProvider)
