from __future__ import annotations

from sqlalchemy.orm import Session

from finmcp.analytics.categories import spend_by_category
from finmcp.analytics.subscriptions import _merchant_key
from finmcp.db.queries import query_transactions
from finmcp.util import month_bounds


def monthly_summary(session: Session, year: int, month: int) -> dict:
    """Resumen del mes: ingresos, gastos, neto, top comercios y categorías."""
    start, end = month_bounds(year, month)
    txs = query_transactions(session, start=start, end=end)

    income = sum(t.amount for t in txs if t.type == "credit")
    expense = sum(t.amount for t in txs if t.type == "debit")

    merchant_totals: dict[str, float] = {}
    for t in txs:
        if t.type != "debit":
            continue
        name = t.merchant_name or t.description
        merchant_totals[name] = merchant_totals.get(name, 0.0) + t.amount
    top_merchants = sorted(
        ({"merchant": k, "total": round(v, 2)} for k, v in merchant_totals.items()),
        key=lambda r: r["total"],
        reverse=True,
    )[:10]

    return {
        "period": f"{year}-{month:02d}",
        "income": round(income, 2),
        "expense": round(expense, 2),
        "net": round(income - expense, 2),
        "transactions": len(txs),
        "by_category": spend_by_category(session, start, end),
        "top_merchants": top_merchants,
    }
