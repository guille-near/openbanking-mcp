from __future__ import annotations

import statistics
from datetime import datetime

from sqlalchemy.orm import Session

from finmcp.analytics.subscriptions import _merchant_key
from finmcp.db.queries import query_transactions

# Factor de consistencia para convertir MAD en un estimador robusto de sigma
# bajo normalidad: 1 / Phi^-1(0.75) ≈ 1.4826.
_MAD_TO_SIGMA = 1.4826


def _mad(values: list[float], med: float) -> float:
    return statistics.median([abs(v - med) for v in values])


def detect_unusual_charges(
    session: Session,
    start: datetime | None = None,
    end: datetime | None = None,
    z_threshold: float = 2.5,
    min_history: int = 3,
) -> list[dict]:
    """Cargos atípicos: importe muy por encima del histórico del comercio.

    Usa mediana + MAD (robustos): a diferencia de media/desviación, el propio
    cargo anómalo no contamina la línea base, así que un único pico grande
    sí se detecta. Si el MAD es 0 (importes idénticos, p.ej. suscripciones),
    cae a un umbral relativo del 50% sobre la mediana.
    """
    history = query_transactions(session, type="debit")
    by_merchant: dict[str, list[float]] = {}
    for t in history:
        by_merchant.setdefault(_merchant_key(t), []).append(t.amount)

    stats: dict[str, tuple[float, float]] = {}  # key -> (median, mad)
    for key, amounts in by_merchant.items():
        if len(amounts) >= min_history:
            med = statistics.median(amounts)
            stats[key] = (med, _mad(amounts, med))

    window = query_transactions(session, start=start, end=end, type="debit")
    flagged: list[dict] = []
    for t in window:
        key = _merchant_key(t)
        if key not in stats:
            continue
        med, mad = stats[key]
        if mad == 0:
            # Sin dispersión: marca solo si supera la mediana en >50%.
            if t.amount > med * 1.5:
                flagged.append(_flag(t, med, None))
            continue
        z = (t.amount - med) / (mad * _MAD_TO_SIGMA)
        if z >= z_threshold and t.amount > med:
            flagged.append(_flag(t, med, round(z, 2)))

    flagged.sort(key=lambda r: (r["z_score"] is not None, r["z_score"] or 0), reverse=True)
    return flagged


def _flag(t, med: float, z: float | None) -> dict:
    return {
        "merchant": t.merchant_name or t.description,
        "amount": round(t.amount, 2),
        "currency": t.currency,
        "date": t.booked_at.date().isoformat(),
        "usual_amount": round(med, 2),
        "z_score": z,
    }
