"""What Fibenchi thinks an asset is, offered rather than imposed.

``classify`` already decides everything a ticker's shape can tell. This
module turns that into a *proposal* about the two stored fields a user can
edit — the asset's type and how its price reads — and answers whether the
proposal disagrees with what's stored.

The policy lives here, in one place, so it can't drift between the create
path and the read path:

- A field the app derived (``FieldSource.AUTO``) may be re-derived and
  offered up when the guess improves.
- A field a human set (``FieldSource.USER``) is never argued with. The
  suggestion is still computed — it just isn't flagged as disagreeing, so
  the UI has nothing to nag about.

Nothing here writes. Stored values change only when a user applies a
suggestion, which is an ordinary update through ``update_asset``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain import AssetRef, UnitKind
from app.domain.provenance import FieldSource
from app.models import Asset, AssetType


@dataclass(frozen=True)
class AssetSuggestion:
    """The shape's read on an asset, plus where it disagrees with the row."""

    type: AssetType
    unit_kind: UnitKind
    currency: str | None
    #: Fields that are AUTO *and* differ from what's stored — i.e. the ones
    #: worth showing the user. A USER-set field never appears here.
    disagrees: frozenset[str] = frozenset()

    @property
    def has_disagreement(self) -> bool:
        return bool(self.disagrees)


def suggest_for(ref: AssetRef) -> AssetSuggestion:
    """The shape's read on a ticker, with no stored row to compare against."""
    if ref.kind.is_index:
        # An index is a rate or a level, never money — so it carries no
        # currency, and unit_kind is the only thing that says how to read it.
        return AssetSuggestion(AssetType.INDEX, ref.unit, None)
    # Shape can't tell an ETF from a stock; that call stays with Yahoo, and
    # STOCK is only the fallback when nothing better is known.
    return AssetSuggestion(AssetType.STOCK, ref.unit, ref.currency)


def suggest_for_asset(asset: Asset) -> AssetSuggestion:
    """The shape's read on a stored asset, flagging only actionable gaps."""
    base = suggest_for(AssetRef(asset.symbol))

    disagrees: set[str] = set()
    # Type: only meaningful for indices. Shape can't distinguish stock from
    # ETF, so proposing STOCK over a stored ETF would be noise, not a finding.
    if (
        asset.type_source.is_auto
        and base.type is AssetType.INDEX
        and asset.type is not AssetType.INDEX
    ):
        disagrees.add("type")
    if asset.unit_source.is_auto and base.unit_kind is not asset.unit_kind:
        disagrees.add("unit_kind")

    return AssetSuggestion(base.type, base.unit_kind, base.currency, frozenset(disagrees))


def source_for(explicit: object | None) -> FieldSource:
    """USER when a caller supplied a value, AUTO when it left the field alone."""
    return FieldSource.USER if explicit is not None else FieldSource.AUTO
