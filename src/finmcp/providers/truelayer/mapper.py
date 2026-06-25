from __future__ import annotations

from datetime import datetime, timezone

from finmcp.providers.types import Account, Balance, Transaction


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def to_account(raw: dict) -> Account:
    account_number = raw.get("account_number") or {}
    return Account(
        provider_account_id=raw["account_id"],
        name=raw.get("display_name") or raw.get("account_type", "Cuenta"),
        type=raw.get("account_type", "TRANSACTION"),
        currency=raw.get("currency", "EUR"),
        iban=account_number.get("iban"),
        raw=raw,
    )


def to_balance(raw: dict) -> Balance:
    return Balance(
        available=raw.get("available"),
        current=raw.get("current"),
        currency=raw.get("currency", "EUR"),
        snapshot_at=_parse_dt(raw.get("update_timestamp")),
        raw=raw,
    )


def to_transaction(raw: dict) -> Transaction:
    amount = float(raw.get("amount", 0.0))
    txn_type = str(raw.get("transaction_type", ""))
    # TrueLayer marca el sentido en transaction_type; algunos feeds usan signo.
    side = "debit" if (txn_type.upper() == "DEBIT" or amount < 0) else "credit"
    classification = raw.get("transaction_classification") or []
    return Transaction(
        provider_id=raw["transaction_id"],
        amount=abs(amount),
        currency=raw.get("currency", "EUR"),
        booked_at=_parse_dt(raw.get("timestamp")),
        description=raw.get("description", ""),
        type=side,
        merchant_name=raw.get("merchant_name"),
        provider_category=classification[0] if classification else None,
        raw=raw,
    )
