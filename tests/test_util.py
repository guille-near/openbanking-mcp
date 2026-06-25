from __future__ import annotations

from datetime import timezone

from finmcp.util import month_bounds, parse_date


def test_parse_date_none():
    assert parse_date(None) is None
    assert parse_date("") is None


def test_parse_date_ymd():
    dt = parse_date("2026-03-15")
    assert (dt.year, dt.month, dt.day) == (2026, 3, 15)
    assert dt.tzinfo == timezone.utc


def test_parse_date_iso_with_z():
    dt = parse_date("2026-03-15T10:30:00Z")
    assert (dt.hour, dt.minute) == (10, 30)
    assert dt.utcoffset().total_seconds() == 0


def test_month_bounds_non_leap_february():
    start, end = month_bounds(2026, 2)
    assert (start.year, start.month, start.day) == (2026, 2, 1)
    assert (end.month, end.day) == (2, 28)  # 2026 no es bisiesto
    assert (end.hour, end.minute, end.second) == (23, 59, 59)


def test_month_bounds_leap_february():
    _, end = month_bounds(2024, 2)
    assert end.day == 29  # 2024 sí es bisiesto
