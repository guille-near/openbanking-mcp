from __future__ import annotations

from sqlalchemy.orm import Session

from finmcp.db import models


def _haystack(tx: models.Transaction, field: str) -> str:
    if field == "merchant":
        return (tx.merchant_name or "").lower()
    if field == "description":
        return (tx.description or "").lower()
    # "any": comercio + concepto
    return f"{tx.merchant_name or ''} {tx.description or ''}".lower()


def _match(tx: models.Transaction, rule: models.CategoryRule) -> bool:
    return rule.pattern.lower() in _haystack(tx, rule.field)


def apply_rules(session: Session, only_uncategorized: bool = False) -> int:
    """Asigna `my_category` según las reglas. Gana la de menor `priority`.

    Devuelve cuántas transacciones cambiaron de categoría.
    """
    rules = (
        session.query(models.CategoryRule)
        .order_by(models.CategoryRule.priority.asc(), models.CategoryRule.id.asc())
        .all()
    )
    if not rules:
        return 0

    q = session.query(models.Transaction)
    if only_uncategorized:
        q = q.filter(models.Transaction.my_category.is_(None))

    changed = 0
    for tx in q.all():
        new_cat = next((r.category for r in rules if _match(tx, r)), None)
        if new_cat is not None and new_cat != tx.my_category:
            tx.my_category = new_cat
            changed += 1
    session.commit()
    return changed
