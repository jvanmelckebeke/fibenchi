"""Emit the companion config JSON Schema — the single source of truth artifact.

This JSON Schema is what the companion app's Zod codegen consumes
(json-schema-to-zod). Regenerate after any change to ``app/schemas/companion.py``
and copy the output into the app repo:

    python -m scripts.export_companion_schema
    # -> backend/companion.schema.json  (copy to fibenchi-app/schema/)
"""

import json
import pathlib

from app.schemas.companion import CompanionConfig


def main() -> None:
    schema = CompanionConfig.model_json_schema(by_alias=True)
    out = pathlib.Path(__file__).resolve().parent.parent / "companion.schema.json"
    out.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
