"""Everything Fibenchi does to a provider frame before anyone reads it.

One pipeline, so a quirk is patched at the boundary and nothing downstream
has to know the provider has quirks. Steps are ordinary
``(df, symbol) -> df`` functions and each one decides for itself whether it
applies, so composing them is just running them in order.

Instrument kinds differ in what they need. Splits are universal — an FX pair
simply never carries a split event. An FX close has to be recovered from the
next bar's open, and asking that of an equity would be wrong rather than
merely useless. So ``BY_KIND`` holds the steps one kind needs and nobody
else's, keyed by the ``AssetKind`` ``classify`` already decided.

Adding a quirk is one entry. If Yahoo turns out to misreport something about
futures, that is ``AssetKind.FUTURE: (fix,)`` here plus the function — no
kind test scattered into the fetch path, and no step left silently guessing
which instruments it is allowed to touch.
"""

from collections.abc import Callable

import pandas as pd

from app.domain.instrument import AssetKind, classify
from app.services.compute.fx_close import recover_fx_close
from app.services.compute.splits import normalize_splits

FrameStep = Callable[[pd.DataFrame, str | None], pd.DataFrame]

# Applied to every frame, in order.
UNIVERSAL: tuple[FrameStep, ...] = (normalize_splits,)

# Applied only to the kind that names them. A kind absent here needs none,
# which is most of them.
BY_KIND: dict[AssetKind, tuple[FrameStep, ...]] = {
    AssetKind.FX: (recover_fx_close,),
}


def steps_for(symbol: str | None) -> tuple[FrameStep, ...]:
    """The steps a symbol's frame goes through, universal ones first."""
    kind = classify(symbol or "").kind
    return (*UNIVERSAL, *BY_KIND.get(kind, ()))


def normalize_frame(df: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    """Run a provider frame through every step that applies to its symbol."""
    for step in steps_for(symbol):
        df = step(df, symbol)
    return df
