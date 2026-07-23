"""Registry-level indicator tests — cross-cutting machinery that exercises the
whole INDICATOR_REGISTRY rather than any single indicator."""

from app.services.compute.indicators import compute_indicators, get_all_output_fields
from tests.helpers import make_price_df as _make_price_df


def test_compute_indicators_columns():
    df = _make_price_df()
    result = compute_indicators(df)
    expected_cols = {"close"} | set(get_all_output_fields())
    assert set(result.columns) == expected_cols


def test_compute_indicators_length():
    df = _make_price_df(100)
    result = compute_indicators(df)
    assert len(result) == 100


def test_atr_adx_in_all_output_fields():
    """ATR and ADX fields should be listed in get_all_output_fields."""
    fields = get_all_output_fields()
    assert "atr" in fields
    assert "adx" in fields
    assert "plus_di" in fields
    assert "minus_di" in fields
