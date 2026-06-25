from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from finmcp.db import models


def list_accounts(session: Session) -> list[models.Account]:
    return session.query(models.Account).all()


def latest_balances(session: Session) -> list[models.Balance]:
    """Último snapshot de saldo por cuenta."""
    subq = (
        session.query(
            models.Balance.account_id,
            func.max(models.Balance.snapshot_at).label("ts"),
        )
        .group_by(models.Balance.account_id)
        .subquery()
    )
    return (
        session.query(models.Balance)
        .join(
            subq,
            (models.Balance.account_id == subq.c.account_id)
            & (models.Balance.snapshot_at == subq.c.ts),
        )
        .all()
    )


def query_transactions(
    session: Session,
    account_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    type: str | None = None,
    text: str | None = None,
    limit: int | None = None,
) -> list[models.Transaction]:
    q = session.query(models.Transaction)
    if account_id:
        q = q.filter(models.Transaction.account_id == account_id)
    if start:
        q = q.filter(models.Transaction.booked_at >= start)
    if end:
        q = q.filter(models.Transaction.booked_at <= end)
    if type:
        q = q.filter(models.Transaction.type == type)
    if text:
        like = f"%{text.lower()}%"
        q = q.filter(
            or_(
                func.lower(models.Transaction.description).like(like),
                func.lower(func.coalesce(models.Transaction.merchant_name, "")).like(
                    like
                ),
            )
        )
    q = q.order_by(models.Transaction.booked_at.desc())
    if limit:
        q = q.limit(limit)
    return q.all()
