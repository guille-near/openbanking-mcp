from __future__ import annotations

from datetime import datetime, timedelta, timezone

from finmcp.analytics.subscriptions import _cadence, detect_subscriptions


def _ago(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def test_cadence_buckets():
    assert _cadence(30) == "mensual"
    assert _cadence(7) == "semanal"
    assert _cadence(14) == "quincenal"
    assert _cadence(90) == "trimestral"
    assert _cadence(365) == "anual"
    assert _cadence(3) == "~3d"


def test_detects_monthly_subscription(make_tx, session):
    for i in range(3):
        make_tx(9.99, merchant="Netflix", booked_at=_ago(30 * i))

    subs = detect_subscriptions(session)

    assert len(subs) == 1
    assert subs[0]["merchant"] == "Netflix"
    assert subs[0]["occurrences"] == 3
    assert subs[0]["cadence"] == "mensual"
    assert subs[0]["amount"] == 9.99


def test_ignores_variable_amounts(make_tx, session):
    # Importes muy dispares -> no parece suscripción
    make_tx(10.0, merchant="Bar", booked_at=_ago(60))
    make_tx(80.0, merchant="Bar", booked_at=_ago(30))
    make_tx(45.0, merchant="Bar", booked_at=_ago(0))

    assert detect_subscriptions(session) == []


def test_ignores_single_charge(make_tx, session):
    make_tx(9.99, merchant="Spotify", booked_at=_ago(0))
    assert detect_subscriptions(session) == []
