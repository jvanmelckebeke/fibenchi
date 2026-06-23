"""Unit tests for the pure thesis aggregate computation (no I/O)."""

from datetime import date, timedelta

from app.services.compute.thesis import aggregate_return_pct, aggregate_return_series


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


# --- aggregate_return_series (the sparkline curve) -------------------------


def test_series_empty():
    assert aggregate_return_series([]) == []
    assert aggregate_return_series([[], []]) == []


def test_series_single_member_curve():
    pts = aggregate_return_series([[
        (date(2026, 3, 1), 100.0),
        (date(2026, 3, 2), 110.0),
        (date(2026, 3, 3), 120.0),
    ]])
    assert pts[0] == {"date": "2026-03-01", "pct": 0.0}   # anchored to the open
    assert pts[-1] == {"date": "2026-03-03", "pct": 20.0}


def test_series_equal_weight_aligned_and_ffilled():
    # A runs day1-3 (100->110->120); B joins day2 (100->110). Each member is
    # anchored to its own first close; B is absent (NaN) on day1, so:
    #   d1 = A only (0%), d2 = mean(+10%, 0%) = 5%, d3 = mean(+20%, +10%) = 15%.
    a = [(date(2026, 3, 1), 100.0), (date(2026, 3, 2), 110.0), (date(2026, 3, 3), 120.0)]
    b = [(date(2026, 3, 2), 100.0), (date(2026, 3, 3), 110.0)]
    by_date = {p["date"]: p["pct"] for p in aggregate_return_series([a, b])}
    assert by_date["2026-03-01"] == 0.0
    assert by_date["2026-03-02"] == 5.0
    assert by_date["2026-03-03"] == 15.0


def test_series_carries_forward_over_gaps():
    # B has no print on day2; its day1 value (0%) carries forward, so day2 is
    # mean(A's +10%, B's carried 0%) = 5% (not A-only).
    a = [(date(2026, 3, 1), 100.0), (date(2026, 3, 2), 110.0)]
    b = [(date(2026, 3, 1), 100.0)]
    by_date = {p["date"]: p["pct"] for p in aggregate_return_series([a, b])}
    assert by_date["2026-03-02"] == 5.0


def test_series_zero_open_member_excluded():
    a = [(date(2026, 3, 1), 0.0), (date(2026, 3, 2), 50.0)]   # zero open -> dropped
    b = [(date(2026, 3, 1), 100.0), (date(2026, 3, 2), 110.0)]
    by_date = {p["date"]: p["pct"] for p in aggregate_return_series([a, b])}
    assert by_date["2026-03-02"] == 10.0


def test_series_downsample_caps_and_keeps_ends():
    closes = [[(date(2026, 1, 1) + timedelta(days=i), 100.0 + i) for i in range(200)]]
    pts = aggregate_return_series(closes, max_points=10)
    assert len(pts) <= 10
    assert pts[0]["date"] == "2026-01-01"
    assert pts[-1]["date"] == (date(2026, 1, 1) + timedelta(days=199)).isoformat()
    assert pts[-1]["pct"] == 199.0   # 100 -> 299 = +199%
