"""Emit the companion JSON Schemas — the single source of truth artifacts.

These JSON Schemas are what the companion app's Zod codegen consumes
(json-schema-to-zod). Regenerate after any change to ``app/schemas/companion.py``
and copy the output into the app repo:

    python -m scripts.export_companion_schema
    # -> backend/companion.schema.json           (copy to fibenchi-app/schema/)
    # -> backend/companion.calendar.schema.json
"""

import json
import pathlib

from app.schemas.companion import CompanionCalendar, CompanionConfig

#: Model -> artifact filename, relative to the backend root.
ARTIFACTS = {
    "companion.schema.json": CompanionConfig,
    "companion.calendar.schema.json": CompanionCalendar,
}


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent
    for filename, model in ARTIFACTS.items():
        out = root / filename
        out.write_text(json.dumps(model.model_json_schema(by_alias=True), indent=2) + "\n")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
