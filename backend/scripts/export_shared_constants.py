"""Emit the constants the web frontend must agree with the backend about.

Two numbers cross the Python/TypeScript boundary and have to match, because
each side acts on the *other* side's behalf:

  - ``SESSION_MATCH_TOL`` — the backend's heal loop refetches a symbol when its
    stored close reconciles with neither the live price nor the previous close.
    That is a prediction about what the frontend will refuse to score. If the
    two tolerances drift, the heal either chases bars the frontend was happy
    with (churn) or leaves σ blank while reporting the symbol healthy.
  - ``VNR_WARMUP_SESSIONS`` — the bar count below which the EWMA vol baseline
    is not trustworthy. The backend enforces it in ``compute_indicators``; the
    frontend needs the same number to explain the blank it gets back.

Until now a comment asked the next reader to keep them in sync by hand, which
is the weakest possible enforcement: nothing fails when it stops being true,
and the symptom (σ blank while the heal insists it fixed the symbol) points at
neither file. This reflects the Python values into a generated TS module, and
CI fails if the checked-in copy no longer matches its source.

Same contract as the other exporters in this directory, one destination
further: those artifacts leave the repo for the companion app, this one is
consumed in-tree by ``frontend/src/lib/sigma.ts``.

    python -m scripts.export_shared_constants
    # -> frontend/src/lib/generated/backend-constants.ts
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

from app.services.compute.indicators import VNR_MAX_SESSIONS_BEHIND, VNR_WARMUP_SESSIONS
from app.services.price_sync import SESSION_MATCH_TOL


@dataclass(frozen=True)
class Constant:
    name: str
    value: float | int
    source: str
    """Where the Python value is defined — the pointer a reader follows back."""
    doc: str


SHARED = [
    Constant(
        name="SESSION_MATCH_TOL",
        value=SESSION_MATCH_TOL,
        source="app/services/price_sync.py",
        doc=(
            "Fractional tolerance for corroborating a session identity from prices.\n"
            "\n"
            "Not the primary test — since #626 both sides carry explicit session\n"
            "dates and identity is exact. This is the fallback for a degraded quote\n"
            "with no `session_date`, or a venue with no calendar.\n"
            "\n"
            "Shared because the backend's trailing-bar heal uses the same tolerance\n"
            "to decide a stored bar is unreconciled and needs refetching. A drift\n"
            "here means the heal and the display disagree about which bars are\n"
            "usable, and σ stays blank on symbols the heal reports as repaired."
        ),
    ),
    Constant(
        name="VNR_MAX_SESSIONS_BEHIND",
        value=VNR_MAX_SESSIONS_BEHIND,
        source="app/services/compute/indicators.py",
        doc=(
            "How many sessions the stored bar may sit behind the live session and\n"
            "still be scored.\n"
            "\n"
            "`vnr_sigma` at bar t forecasts session t+1, so a bar N sessions behind\n"
            "carries a forecast that missed N-1 EWMA updates. The numerator is\n"
            "unaffected at any distance: the quote's `change_percent` is measured\n"
            "against the true previous close, so it stays a verified single-session\n"
            "return however stale our own bars are. Only the denominator ages, which\n"
            "is why this is a bound rather than a blank.\n"
            "\n"
            "Shared because the backend sizes the session window it ships on each\n"
            "quote from this number — the window has to contain every distance the\n"
            "frontend is willing to accept."
        ),
    ),
    Constant(
        name="VNR_WARMUP_SESSIONS",
        value=VNR_WARMUP_SESSIONS,
        source="app/services/compute/indicators.py",
        doc=(
            "Sessions of history before the EWMA vol baseline is trustworthy.\n"
            "\n"
            "Enforced backend-side in `compute_indicators`, which returns no σ\n"
            "below this. The frontend needs the same number to say *why* the\n"
            "column is blank rather than just leaving a dash."
        ),
    ),
]

HEADER = """\
// GENERATED FILE — do not edit by hand.
//
// Source of truth is Python. Regenerate with:
//
//     cd backend && python -m scripts.export_shared_constants
//
// CI regenerates this file and fails if it moves, so an edit here without a
// matching change on the Python side cannot merge.
"""


def _ts_number(value: float | int) -> str:
    """Render a Python number as a TS numeric literal.

    ``repr`` is right for both int and float here (0.005 -> "0.005", 60 ->
    "60") but would emit exponent forms for extreme magnitudes; nothing shared
    is anywhere near that, and this asserts rather than silently emitting a
    literal that reads differently in the two languages.
    """
    text = repr(value)
    assert "e" not in text and "E" not in text, f"exponent form is not portable enough: {text}"
    return text


def _render(constants: list[Constant]) -> str:
    blocks = [HEADER]
    for c in constants:
        doc = "\n".join(f" * {line}".rstrip() for line in c.doc.splitlines())
        blocks.append(
            f"/**\n{doc}\n *\n * @see backend/{c.source}\n */\n"
            f"export const {c.name} = {_ts_number(c.value)}\n"
        )
    return "\n".join(blocks)


def main() -> None:
    # __file__-relative, so the artifact lands in the same place from any cwd.
    out = (
        pathlib.Path(__file__).resolve().parents[2]
        / "frontend/src/lib/generated/backend-constants.ts"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_render(SHARED), encoding="utf-8")
    print(f"wrote {out} ({len(SHARED)} constants)")


if __name__ == "__main__":
    main()
