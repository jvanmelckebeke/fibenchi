"""Probe how many upstream HTTP calls each YahooClient method actually makes.

Monkey-patches ``requests.Session.send`` to count + log URLs (host + path),
then invokes each client method on a single live symbol and reports the
HTTP-call count. This is the only way to verify yahooquery's actual fan-out
behavior — whether it coalesces quoteSummary modules into one request or
fires them separately.

Run inside the backend container:
    docker compose exec backend python scripts/probe_yahoo_calls.py

Makes ~20-30 real network calls to query2.finance.yahoo.com. Throwaway.
"""
from __future__ import annotations

import asyncio
import sys
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from curl_cffi import requests as curl_requests

# Add backend root so ``app`` imports work when invoked from /app/scripts.
sys.path.insert(0, "/app")

# Counter is updated by the patched request().
_counter: dict[str, list[str]] = defaultdict(list)
_active_label: str | None = None

_orig_request = curl_requests.Session.request


def _patched_request(self, method, url, *args, **kwargs):
    if _active_label is not None:
        parsed = urlparse(url)
        path = parsed.path
        # Strip noisy/sensitive query params; keep ones that disambiguate endpoints.
        q = parsed.query or ""
        keep = [
            p for p in q.split("&")
            if p.startswith(("modules=", "interval=", "range=", "period1=", "period2="))
        ]
        suffix = ("?" + "&".join(keep)) if keep else ""
        _counter[_active_label].append(f"{method} {parsed.netloc}{path}{suffix}")
    return _orig_request(self, method, url, *args, **kwargs)


curl_requests.Session.request = _patched_request


@asynccontextmanager
async def measure(label: str):
    global _active_label
    _active_label = label
    t0 = time.monotonic()
    try:
        yield
    finally:
        elapsed = time.monotonic() - t0
        urls = _counter[label]
        print(f"\n[{label}] {len(urls)} HTTP call(s) in {elapsed:.2f}s")
        for u in urls:
            print(f"  → {u}")
        _active_label = None


async def main():
    # Use a no-op throttle so we measure raw fan-out, not throttle spacing.
    from app.services.yahoo.client import YahooClient
    from app.services.yahoo.rate_limit import YahooThrottle

    class NoopThrottle(YahooThrottle):
        def __init__(self):
            super().__init__(min_interval=0.0)

    client = YahooClient(throttle=NoopThrottle())

    print("=" * 70)
    print("Probing YahooClient HTTP fan-out (no throttle, real network)")
    print("=" * 70)

    async with measure("validate(AAPL)"):
        await client.validate("AAPL")

    async with measure("quotes([AAPL])"):
        await client.quotes(["AAPL"])

    async with measure("quotes([AAPL]) again (cached?)"):
        await client.quotes(["AAPL"])

    async with measure("currencies([AAPL])"):
        await client.currencies(["AAPL"])

    async with measure("history(AAPL, 1mo)"):
        await client.history("AAPL", period="1mo")

    async with measure("batch_history([AAPL,MSFT], 1mo)"):
        await client.batch_history(["AAPL", "MSFT"], period="1mo")

    async with measure("fundamentals([AAPL])"):
        await client.fundamentals(["AAPL"])

    async with measure("earnings(AAPL)"):
        await client.earnings("AAPL")

    async with measure("intraday([AAPL])"):
        await client.intraday(["AAPL"])

    async with measure("holdings(SPY)"):
        await client.holdings("SPY")

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"{'method':<40} {'http calls':>10}")
    print("-" * 52)
    for label, urls in _counter.items():
        print(f"{label:<40} {len(urls):>10}")


if __name__ == "__main__":
    asyncio.run(main())
