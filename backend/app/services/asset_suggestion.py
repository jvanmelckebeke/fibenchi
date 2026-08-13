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
from typing import Protocol

from app.domain import AssetRef, UnitKind
from app.domain.provenance import FieldSource
from app.models import Asset, AssetType


class Classified(Protocol):
    """The fields a suggestion is computed from.

    A Protocol rather than ``Asset`` because ``AssetResponse`` carries exactly
    these too, and deriving the suggestion in the response schema is what stops
    it depending on which router happened to remember to attach it.
    """

    symbol: str
    type: AssetType
    unit_kind: UnitKind
    type_source: FieldSource
    unit_source: FieldSource


@dataclass(frozen=True)
class AssetSuggestion:
    """The shape's read on an asset, plus where it disagrees with the row."""

    type: AssetType
    unit_kind: UnitKind
    currency: str | None
    #: Fields where the shape meaningfully differs from what's stored,
    #: regardless of who stored it. This is what makes a value *resettable*.
    differs: frozenset[str] = frozenset()
    #: The subset of ``differs`` that is still AUTO — i.e. what Fibenchi may
    #: raise unprompted. A field the user set never appears here, however much
    #: the shape disagrees with it; going looking for that is the user's move,
    #: which is why ``differs`` is exposed separately.
    disagrees: frozenset[str] = frozenset()


def suggest_for(ref: AssetRef) -> AssetSuggestion:
    """The shape's read on a ticker, with no stored row to compare against."""
    if ref.kind.is_index:
        # An index is a rate or a level, never money — so it carries no
        # currency, and unit_kind is the only thing that says how to read it.
        return AssetSuggestion(AssetType.INDEX, ref.unit, None)
    # Shape can't tell an ETF from a stock; that call stays with Yahoo, and
    # STOCK is only the fallback when nothing better is known.
    return AssetSuggestion(AssetType.STOCK, ref.unit, ref.currency)


def suggest_for_asset(asset: Classified) -> AssetSuggestion:
    """The shape's read on a stored asset, and where it differs from the row."""
    base = suggest_for(AssetRef(asset.symbol))

    differs: set[str] = set()
    # Type: only meaningful for indices. Shape can't distinguish stock from
    # ETF, so proposing STOCK over a stored ETF would be noise, not a finding.
    if base.type is AssetType.INDEX and asset.type is not AssetType.INDEX:
        differs.add("type")
    if base.unit_kind is not asset.unit_kind:
        differs.add("unit_kind")

    # Provenance gates only the *unprompted* half. A user-set field stays in
    # ``differs`` so it remains resettable and can be shown on request —
    # "don't argue with you" must not collapse into "never speak again".
    source = {"type": asset.type_source, "unit_kind": asset.unit_source}
    disagrees = {f for f in differs if source[f].is_auto}

    return AssetSuggestion(
        base.type, base.unit_kind, base.currency, frozenset(differs), frozenset(disagrees),
    )


async def reset_detection(asset: Asset, fields: set[str]) -> None:
    """Hand a field back to auto-detection: adopt the shape's answer, and
    clear the provenance so future improvements are picked up again.

    ``currency`` is deliberately not reset. The shape's currency is a
    *fallback* inferred from the venue suffix — Yahoo's answer is better, and
    an index's currency is inert anyway once unit_kind says the number isn't
    money. Resetting it could only make things worse.
    """
    base = suggest_for(AssetRef(asset.symbol))
    if "type" in fields:
        asset.type = base.type
        asset.type_source = FieldSource.AUTO
    if "unit_kind" in fields:
        asset.unit_kind = base.unit_kind
        asset.unit_source = FieldSource.AUTO


def source_for(explicit: object | None) -> FieldSource:
    """USER when a caller supplied a value, AUTO when it left the field alone."""
    return FieldSource.USER if explicit is not None else FieldSource.AUTO
