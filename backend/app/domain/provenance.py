"""Where a stored field's value came from.

Only two answers matter: the app worked it out, or a human said so. That
distinction is what lets a recommendation stay a recommendation — a field
Fibenchi guessed can be re-guessed and offered up when the guess improves,
while a field you chose is never second-guessed at you.

Without it the choice collapses to overwrite-everything or
overwrite-nothing, which is how six index assets sat mistyped for months:
nothing could tell "Yahoo said stock once" from "the user means stock".
"""

from __future__ import annotations

from enum import Enum


class FieldSource(str, Enum):
    AUTO = "auto"   # derived by Fibenchi; safe to re-derive and re-suggest
    USER = "user"   # set deliberately by a human; suggestions stay quiet

    @property
    def is_auto(self) -> bool:
        return self is FieldSource.AUTO
