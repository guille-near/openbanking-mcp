from __future__ import annotations

from finmcp.analytics.anomalies import detect_unusual_charges


def test_flags_spike_with_robust_mad(make_tx, session):
    # Historial estable con algo de dispersión + un pico claro.
    for amt in (10.0, 12.0, 11.0, 9.0, 10.0, 13.0):
        make_tx(amt, merchant="Luz")
    make_tx(100.0, merchant="Luz")  # anómalo

    flagged = detect_unusual_charges(session)

    luz = [f for f in flagged if f["merchant"] == "Luz" and f["amount"] == 100.0]
    assert len(luz) == 1
    assert luz[0]["z_score"] is not None and luz[0]["z_score"] >= 2.5


def test_zero_mad_uses_relative_threshold(make_tx, session):
    # Importes idénticos -> MAD=0 -> umbral relativo del 50%.
    for _ in range(4):
        make_tx(10.0, merchant="Cuota")
    make_tx(100.0, merchant="Cuota")  # > mediana * 1.5

    flagged = detect_unusual_charges(session)
    cuota = [f for f in flagged if f["merchant"] == "Cuota" and f["amount"] == 100.0]
    assert len(cuota) == 1
    assert cuota[0]["z_score"] is None  # marcado por la regla relativa


def test_stable_subscription_not_flagged(make_tx, session):
    for _ in range(6):
        make_tx(9.99, merchant="Netflix")

    flagged = detect_unusual_charges(session)
    assert all(f["merchant"] != "Netflix" for f in flagged)


def test_respects_min_history(make_tx, session):
    # Solo 2 cargos: por debajo de min_history (3) -> nunca se evalúa.
    make_tx(10.0, merchant="Nuevo")
    make_tx(500.0, merchant="Nuevo")

    flagged = detect_unusual_charges(session)
    assert all(f["merchant"] != "Nuevo" for f in flagged)
