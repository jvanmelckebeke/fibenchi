"""How big is the first `intraday` SSE frame?

Background: `quote_event_generator` pushes deltas, except on its first
iteration — there `last_intraday_ts` is empty so the whole bar set for every
grouped asset goes out in one `event: intraday`. Every browser tab that opens
(or reconnects) pays that frame. Nothing measured it; #615 asked for a number
before deciding whether it needs windowing.

This reproduces the first iteration exactly: the same roster query, the same
`get_intraday_bars`, the same `TypeAdapter.dump_json`. It reads the live DB
and makes no upstream calls, so it is safe to run any time — but the number
it prints is only as realistic as the roster and the intraday table behind
it. Run it late in a session, not on a freshly-wiped intraday table.

    docker compose exec backend python scripts/probe_sse_first_frame.py
    docker compose exec backend python scripts/probe_sse_first_frame.py --toon
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import sys

sys.path.insert(0, "/app")


def _human(n: int) -> str:
    return f"{n / 1024:.1f} KiB" if n >= 1024 else f"{n} B"


async def collect() -> dict:
    from sqlalchemy import func, select

    from app.database import async_session
    from app.models.group import Group, group_assets
    from app.repositories.asset_repo import AssetRepository
    from app.services.intraday import get_intraday_bars
    from app.services.quote_service import (
        _intraday_payload_adapter,
        _quotes_payload_adapter,
    )

    async with async_session() as db:
        refs = await AssetRepository(db).list_in_any_group_refs()
        all_bars = await get_intraday_bars(db, refs)
        # The stream's roster is every grouped asset, but a page renders one
        # group. The biggest group bounds what any single view can consume —
        # the gap is bars nobody on that page will draw.
        biggest = (await db.execute(
            select(Group.name, func.count(group_assets.c.asset_id).label("n"))
            .join(group_assets, group_assets.c.group_id == Group.id)
            .group_by(Group.id)
            .order_by(func.count(group_assets.c.asset_id).desc())
            .limit(1)
        )).first()

    frame = _intraday_payload_adapter.dump_json(all_bars)
    # The bytes actually written to the socket, not just the JSON.
    wire = len(b"event: intraday\ndata: " + frame + b"\n\n")

    per_symbol = sorted(
        (
            {
                "symbol": sym,
                "bars": len(bars),
                "bytes": len(_intraday_payload_adapter.dump_json({sym: bars})),
            }
            for sym, bars in all_bars.items()
        ),
        key=lambda r: r["bytes"],
        reverse=True,
    )

    # One quotes frame for scale — that one is a delta after the first push,
    # so it is the recurring cost the intraday frame should be judged against.
    quotes_bytes = len(_quotes_payload_adapter.dump_json({}))

    return {
        "roster": len(refs),
        "symbols_with_bars": len(all_bars),
        "bars": sum(len(b) for b in all_bars.values()),
        "frame_bytes": wire,
        "frame_gzip_bytes": len(gzip.compress(frame)),
        "empty_quotes_frame_bytes": quotes_bytes,
        "biggest_group": biggest[0] if biggest else None,
        "biggest_group_size": biggest[1] if biggest else 0,
        "per_symbol": per_symbol,
    }


def format_toon(d: dict) -> str:
    lines = [
        f"roster: {d['roster']}",
        f"symbols_with_bars: {d['symbols_with_bars']}",
        f"bars: {d['bars']}",
        f"frame_bytes: {d['frame_bytes']}",
        f"frame_gzip_bytes: {d['frame_gzip_bytes']}",
        f"per_symbol[{len(d['per_symbol'])}]{{symbol,bars,bytes}}:",
    ]
    lines += [f"  {r['symbol']},{r['bars']},{r['bytes']}" for r in d["per_symbol"]]
    return "\n".join(lines)


def format_human(d: dict) -> str:
    out = [
        "First `event: intraday` frame",
        "=" * 60,
        f"  roster                {d['roster']} grouped assets",
        f"  with bars             {d['symbols_with_bars']}",
        f"  biggest group         {d['biggest_group_size']} ({d['biggest_group']})"
        f" — a page can render at most this many",
        f"  bars total            {d['bars']}",
        f"  frame on the wire     {_human(d['frame_bytes'])}  ({d['frame_bytes']} B)",
        f"  gzipped               {_human(d['frame_gzip_bytes'])}"
        "   (no GZipMiddleware today — SSE is sent raw)",
        "",
        f"  bytes per bar         {d['frame_bytes'] / max(d['bars'], 1):.0f}",
        "",
        "Heaviest symbols",
        "-" * 60,
    ]
    for r in d["per_symbol"][:15]:
        out.append(f"  {r['symbol']:<14} {r['bars']:>5} bars   {_human(r['bytes'])}")
    if len(d["per_symbol"]) > 15:
        out.append(f"  … {len(d['per_symbol']) - 15} more")
    return "\n".join(out)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--toon", action="store_true", help="TOON output: token-efficient format")
    g.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    data = await collect()
    if args.toon:
        print(format_toon(data))
    elif args.json:
        import json

        print(json.dumps(data, indent=2))
    else:
        print(format_human(data))


if __name__ == "__main__":
    asyncio.run(main())
