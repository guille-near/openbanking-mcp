from __future__ import annotations

from datetime import datetime, timezone

from finmcp.analytics.summaries import monthly_summary


def _d(day: int) -> datetime:
    return datetime(2026, 3, day, 12, 0, tzinfo=timezone.utc)


def test_monthly_summary_totals_and_top(make_tx, session):
    make_tx(2000.0, type="credit", merchant="Nómina", booked_at=_d(1))
    make_tx(50.0, type="debit", merchant="Mercadona", booked_at=_d(5))
    make_tx(30.0, type="debit", merchant="Mercadona", booked_at=_d(10))
    make_tx(100.0, type="debit", merchant="Zara", booked_at=_d(15))
    # Fuera del mes: no debe contar
    make_tx(999.0, type="debit", merchant="Otro", booked_at=datetime(2026, 4, 1, tzinfo=timezone.utc))

    s = monthly_summary(session, 2026, 3)

    assert s["period"] == "2026-03"
    assert s["income"] == 2000.0
    assert s["expense"] == 180.0
    assert s["net"] == 1820.0
    assert s["transactions"] == 4
    # top_merchants ordenado por gasto desc, solo débitos
    top = s["top_merchants"]
    assert top[0] == {"merchant": "Zara", "total": 100.0}
    assert top[1] == {"merchant": "Mercadona", "total": 80.0}
    assert all(m["merchant"] != "Nómina" for m in top)
