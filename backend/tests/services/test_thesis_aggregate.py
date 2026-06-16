"""Unit tests for the pure thesis aggregate computation (no I/O)."""

from app.services.compute.thesis import aggregate_return_pct


def test_empty_returns_none():
    assert aggregate_return_pct([]) is None
    assert aggregate_return_pct([[], []]) is None


def test_single_member_return():
    # 100 -> 120 = +20%
    assert aggregate_return_pct([[100.0, 110.0, 120.0]]) == 20.0


def test_equal_weight_mean():
    # A: 100 -> 120 (+20%), B: 100 -> 110 (+10%); mean = 15%
    assert aggregate_return_pct([[100.0, 120.0], [100.0, 110.0]]) == 15.0


def test_negative_and_positive_mix():
    # A: 100 -> 90 (-10%), B: 100 -> 130 (+30%); mean = +10%
    assert aggregate_return_pct([[100.0, 90.0], [100.0, 130.0]]) == 10.0


def test_base_is_first_close_not_min_or_last():
    # the anchor is the FIRST close (the open date), not a later dip
    assert aggregate_return_pct([[100.0, 80.0, 120.0]]) == 20.0


def test_member_without_prices_excluded():
    # A contributes (+20%), B has no prices since open -> mean over A only
    assert aggregate_return_pct([[100.0, 120.0], []]) == 20.0


def test_zero_open_excluded():
    assert aggregate_return_pct([[0.0, 50.0]]) is None
    # zero-open member excluded; the valid member still counts
    assert aggregate_return_pct([[0.0, 50.0], [100.0, 110.0]]) == 10.0


def test_rounds_to_two_dp():
    # 100 -> 133.333 ≈ +33.33%
    assert aggregate_return_pct([[100.0, 133.333]]) == 33.33
