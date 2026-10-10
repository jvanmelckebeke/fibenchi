"""Emit the companion JSON Schemas — the single source of truth artifacts.

The contract package (``contract/``) turns these JSON Schemas into the Zod schemas
the companion app validates with. Regenerate after any change to
``app/schemas/companion.py``, commit the output, and bump the version in
``contract/package.json``:

    python -m scripts.export_companion_schema
    # -> backend/companion.schema.json
    # -> backend/companion.calendar.schema.json
    # -> backend/companion.portfolio-index.schema.json
    # -> backend/companion.pulse.schema.json
"""

import json
import pathlib

from app.schemas.companion import CompanionCalendar, CompanionConfig, CompanionPortfolioIndex, CompanionPulse

#: Model -> artifact filename, relative to the backend root.
ARTIFACTS = {
    "companion.schema.json": CompanionConfig,
    "companion.calendar.schema.json": CompanionCalendar,
    "companion.portfolio-index.schema.json": CompanionPortfolioIndex,
    "companion.pulse.schema.json": CompanionPulse,
}


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent
    for filename, model in ARTIFACTS.items():
        out = root / filename
        out.write_text(json.dumps(model.model_json_schema(by_alias=True), indent=2) + "\n")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
