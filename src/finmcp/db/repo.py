from __future__ import annotations

from sqlalchemy.orm import Session

from finmcp.db import models
from finmcp.providers.types import Account, Balance, Transaction


def upsert_account(session: Session, acc: Account) -> None:
    row = session.get(models.Account, acc.provider_account_id)
    if row is None:
        row = models.Account(id=acc.provider_account_id)
        session.add(row)
    row.name = acc.name
    row.type = acc.type
    row.currency = acc.currency
    row.iban = acc.iban
    row.raw_json = acc.raw


def add_balance(session: Session, account_id: str, bal: Balance) -> None:
    session.add(
        models.Balance(
            account_id=account_id,
            available=bal.available,
            current=bal.current,
            currency=bal.currency,
            snapshot_at=bal.snapshot_at,
        )
    )


def upsert_transaction(
    session: Session, account_id: str, tx: Transaction
) -> bool:
    """Upsert idempotente por id de proveedor. Devuelve True si es nueva."""
    existing = session.get(models.Transaction, tx.provider_id)
    is_new = existing is None
    if existing is None:
        existing = models.Transaction(id=tx.provider_id, account_id=account_id)
        session.add(existing)
    existing.amount = tx.amount
    existing.currency = tx.currency
    existing.booked_at = tx.booked_at
    existing.description = tx.description
    existing.type = tx.type
    existing.merchant_name = tx.merchant_name
    existing.provider_category = tx.provider_category
    # Preserva my_category si ya había una recategorización manual.
    existing.raw_json = tx.raw
    return is_new
