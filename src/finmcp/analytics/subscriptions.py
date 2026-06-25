from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from finmcp.db.queries import query_transactions


def _merchant_key(tx) -> str:
    return (tx.merchant_name or tx.description or "Desconocido").strip().lower()


def _cadence(median_days: float) -> str:
    if 25 <= median_days <= 35:
        return "mensual"
    if 6 <= median_days <= 8:
        return "semanal"
    if 13 <= median_days <= 16:
        return "quincenal"
    if 85 <= median_days <= 95:
        return "trimestral"
    if 350 <= median_days <= 380:
        return "anual"
    return f"~{round(median_days)}d"


def detect_subscriptions(
    session: Session,
    lookback_months: int = 6,
    amount_tolerance: float = 0.15,
) -> list[dict]:
    """Detecta cargos recurrentes (suscripciones/domiciliaciones).

    Heurística: mismo comercio con >=2 cargos, importe estable (variación
    relativa < amount_tolerance) y una cadencia regular.
    """
    start = datetime.now(timezone.utc) - timedelta(days=30 * lookback_months)
    txs = query_transactions(session, start=start, type="debit")

    groups: dict[str, list] = {}
    for t in txs:
        groups.setdefault(_merchant_key(t), []).append(t)

    subs: list[dict] = []
    for key, items in groups.items():
        if len(items) < 2:
            continue
        amounts = [i.amount for i in items]
        mean_amt = statistics.mean(amounts)
        if mean_amt == 0:
            continue
        spread = (max(amounts) - min(amounts)) / mean_amt
        if spread > amount_tolerance:
            continue  # importe demasiado variable -> no parece suscripción

        dates = sorted(i.booked_at for i in items)
        diffs = [
            (dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)
        ]
        median_gap = statistics.median(diffs) if diffs else 0
        subs.append(
            {
                "merchant": items[0].merchant_name or items[0].description,
                "amount": round(mean_amt, 2),
                "currency": items[0].currency,
                "occurrences": len(items),
                "cadence": _cadence(median_gap),
                "last_charge": dates[-1].date().isoformat(),
            }
        )
    subs.sort(key=lambda s: s["amount"], reverse=True)
    return subs
