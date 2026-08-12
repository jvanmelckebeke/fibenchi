"""Emit the indicator contract + golden fixtures — cross-language SoT artifacts.

``indicators.py`` is the source of truth for technical-indicator definitions and
their numeric kernels. The companion app (fibenchi-app, React Native/TS) re-
implements a subset of these kernels by hand. To keep the two from drifting,
this script reflects the registry outward as two language-neutral artifacts:

  1. ``indicator.contract.json`` — registry *metadata* (no Python callables):
     which indicators exist, their kernel id, params, kernel output fields,
     warmup, decimals, a snapshot-derived tag, and a ``platforms`` tag so the app
     can implement a deliberate subset without silent drift.
  2. ``indicator.fixtures.json`` — a fixed synthetic OHLC series run through the
     pandas reference, with expected per-bar series + snapshot. The app golden-
     tests its TS kernels against this (pins EMA ``adjust=False`` / Wilder alpha).

Regenerate after changing ``indicators.py``, then copy both into the app repo:

    python -m scripts.export_indicator_contract
    # -> backend/indicator.contract.json   (copy to fibenchi-app/schema/)
    # -> backend/indicator.fixtures.json    (copy to fibenchi-app/lib/compute/__fixtures__/)
"""

from __future__ import annotations

import json
import math
import pathlib

import numpy as np
import pandas as pd

from app.services.compute.indicators import (
    INDICATOR_REGISTRY,
    IndicatorDef,
    build_indicator_snapshot,
    compute_indicators,
)

# Indicators the companion app implements today. Everything else is web-only;
# promoting one to the app is a matter of adding it here + writing the TS kernel.
APP_INDICATORS = {"rsi", "sma_20", "sma_50", "macd", "vnr"}

# App-relevant fields for the golden fixtures. The app computes neither the
# *_delta / *_delta_sigma analysis fields nor the web-only indicators.
#
# ``vnr_sigma`` is the exception to "the app skips the companion fields": it is
# the forward vol forecast the app divides a live intraday return by to score
# today's move before its bar is written, so its EWMA recursion needs pinning
# too. ``vnr_gap_sessions`` is not fixtured — the synthetic series has a
# RangeIndex, so ``session_gap_days`` reports no gap information and the column
# is null throughout; there is nothing to pin.
APP_SERIES_FIELDS = ["rsi", "sma_20", "sma_50", "macd", "macd_signal", "macd_hist", "vnr", "vnr_sigma"]
APP_SNAPSHOT_FIELDS = [*APP_SERIES_FIELDS, "macd_signal_dir"]

CONTRACT_VERSION = 1
FIXTURE_BARS = 160


def _kernel_fields(defn: IndicatorDef) -> list[str]:
    """Fields the kernel func produces directly (excludes post-computed deltas)."""
    if defn.result_mapping:
        return list(defn.result_mapping.values())
    return defn.output_fields[:1]


def _snapshot_tag(defn: IndicatorDef) -> str | None:
    """Stable string id for the snapshot-derived callback (drops Python naming)."""
    if defn.snapshot_derived is None:
        return None
    return defn.snapshot_derived.__name__.strip("_").removesuffix("_snapshot_derived")


def _build_contract() -> dict:
    indicators = []
    for key, defn in INDICATOR_REGISTRY.items():
        kernel_fields = _kernel_fields(defn)
        delta_fields = [f for f in defn.output_fields if f not in kernel_fields]
        indicators.append(
            {
                "key": key,
                "kernel": defn.func.__name__,
                "params": dict(defn.params),
                "outputFields": kernel_fields,
                "deltaFields": delta_fields,
                "decimals": defn.decimals,
                "fieldDecimals": dict(defn.field_decimals),
                "warmup": defn.warmup_periods,
                "usesOhlc": defn.uses_ohlc,
                "snapshotDerived": _snapshot_tag(defn),
                "platforms": ["web", "app"] if key in APP_INDICATORS else ["web"],
            }
        )
    return {"version": CONTRACT_VERSION, "indicators": indicators}


def _synthetic_ohlc(n: int = FIXTURE_BARS) -> pd.DataFrame:
    """Deterministic OHLC series (no RNG) — exercises the kernels reproducibly."""
    t = np.arange(n, dtype=float)
    close = 100 + 10 * np.sin(t / 9) + 0.05 * t + 2 * np.sin(t / 2.3)
    open_ = close - 0.3 * np.sin(t / 3)
    high = np.maximum(open_, close) + 0.5 + 0.2 * np.abs(np.sin(t / 1.7))
    low = np.minimum(open_, close) - 0.5 - 0.2 * np.abs(np.cos(t / 1.9))
    volume = 1_000_000 + 200_000 * np.sin(t / 5) + 500 * t
    return pd.DataFrame(
        {
            "open": open_.round(4),
            "high": high.round(4),
            "low": low.round(4),
            "close": close.round(4),
            "volume": volume.round(0),
        }
    )


def _clean(value) -> float | None:
    """NaN/inf → None so the JSON is valid for JS ``JSON.parse``."""
    f = float(value)
    return f if math.isfinite(f) else None


def _build_fixtures() -> dict:
    df = _synthetic_ohlc()
    base_time = 1_700_000_000  # fixed epoch seconds; one daily bar apart
    bars = [
        {
            "time": base_time + i * 86_400,
            "open": float(df["open"].iloc[i]),
            "high": float(df["high"].iloc[i]),
            "low": float(df["low"].iloc[i]),
            "close": float(df["close"].iloc[i]),
            "volume": float(df["volume"].iloc[i]),
        }
        for i in range(len(df))
    ]

    computed = compute_indicators(df)
    series = {f: [_clean(v) for v in computed[f]] for f in APP_SERIES_FIELDS}

    snap = build_indicator_snapshot(computed)
    snapshot = {
        "close": snap.close,
        "changePct": snap.change_pct,
        "values": {f: snap.values.get(f) for f in APP_SNAPSHOT_FIELDS},
    }

    return {"input": bars, "expected": {"series": series, "snapshot": snapshot}}


def main() -> None:
    out_dir = pathlib.Path(__file__).resolve().parent.parent
    contract = out_dir / "indicator.contract.json"
    fixtures = out_dir / "indicator.fixtures.json"
    contract.write_text(json.dumps(_build_contract(), indent=2) + "\n")
    fixtures.write_text(json.dumps(_build_fixtures(), indent=2) + "\n")
    print(f"wrote {contract}")
    print(f"wrote {fixtures}")


if __name__ == "__main__":
    main()
