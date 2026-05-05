"""Does yahooquery reuse session bootstrap across calls?

Background: each `_ticker()` invocation in YahooClient builds a fresh
`Ticker(symbols)`. The first probe showed every call pays ~3 setup HTTP
requests (consent + crumb). This script tests two things:

1. Does a single Ticker instance reuse its session across multiple endpoint
   accesses (e.g. `t.price` then `t.history(...)` later)?
2. Does the YahooClient pay the 3-call setup tax on EVERY `_call`?
"""
from __future__ import annotations

import asyncio
import sys
from urllib.parse import urlparse

from curl_cffi import requests as curl_requests

sys.path.insert(0, "/app")

_calls: list[tuple[str, str]] = []
_label = "global"

_orig = curl_requests.Session.request


def _patched(self, method, url, *args, **kwargs):
    parsed = urlparse(url)
    _calls.append((_label, f"{method} {parsed.netloc}{parsed.path}"))
    return _orig(self, method, url, *args, **kwargs)


curl_requests.Session.request = _patched


def show(after_label: str):
    print(f"\n--- {after_label} ---")
    matching = [c for l, c in _calls if l == after_label]
    print(f"  {len(matching)} HTTP call(s)")
    for c in matching:
        print(f"    → {c}")


async def main():
    global _label
    from yahooquery import Ticker
    from app.services.yahoo.client import YahooClient
    from app.services.yahoo.rate_limit import YahooThrottle

    class NoopThrottle(YahooThrottle):
        def __init__(self):
            super().__init__(min_interval=0.0)

    print("=" * 70)
    print("Test 1: Single Ticker instance, multiple endpoint accesses")
    print("=" * 70)

    _label = "Ticker(AAPL).price (#1)"
    t = Ticker("AAPL")
    _ = t.price
    show(_label)

    _label = "Ticker(AAPL).price (#2 same instance)"
    _ = t.price
    show(_label)

    _label = "Ticker(AAPL).key_stats (same instance)"
    _ = t.key_stats
    show(_label)

    _label = "Ticker(AAPL).history (same instance)"
    _ = t.history(period="1mo")
    show(_label)

    print("\n" + "=" * 70)
    print("Test 2: YahooClient — does each _call pay session bootstrap?")
    print("=" * 70)

    client = YahooClient(throttle=NoopThrottle())

    _label = "client.quotes #1"
    await client.quotes(["AAPL"])
    show(_label)

    # Wait past quote cache TTL to force a real upstream call
    await asyncio.sleep(13)

    _label = "client.quotes #2 (after cache expiry)"
    await client.quotes(["AAPL"])
    show(_label)

    _label = "client.quotes #3 (different symbol = bypass cache)"
    await client.quotes(["MSFT"])
    show(_label)


if __name__ == "__main__":
    asyncio.run(main())
