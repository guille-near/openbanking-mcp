from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from finmcp.db.queries import query_transactions

UNCATEGORIZED = "Sin categoría"


def category_of(tx) -> str:
    return tx.my_category or tx.provider_category or UNCATEGORIZED


def spend_by_category(
    session: Session,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict]:
    """Gasto (débitos) agregado por categoría, de mayor a menor."""
    txs = query_transactions(session, start=start, end=end, type="debit")
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for t in txs:
        cat = category_of(t)
        totals[cat] = totals.get(cat, 0.0) + t.amount
        counts[cat] = counts.get(cat, 0) + 1
    rows = [
        {"category": cat, "total": round(total, 2), "count": counts[cat]}
        for cat, total in totals.items()
    ]
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows
