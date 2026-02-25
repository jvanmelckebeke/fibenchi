"""Shared Pydantic field validators."""

import re

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_hex_color(v: str) -> str:
    """Validate that a string is a valid 6-digit hex colour code."""
    if not HEX_COLOR_RE.match(v):
        raise ValueError("color must be a valid hex code (e.g. '#3b82f6')")
    return v
