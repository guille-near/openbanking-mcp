from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from finmcp.providers.types import Account, Balance, Transaction

# Enable Banking usa códigos Berlin Group para el tipo de saldo.
_AVAILABLE = {"ITAV", "FWAV"}  # interim/forward available
_CURRENT = {"CLBD", "ITBD", "XPCD", "OPBD", "PRCD"}  # closing/interim booked, etc.


def to_account(a: dict) -> Account:
    acct_id = a.get("account_id") or {}
    return Account(
        provider_account_id=a["uid"],
        name=a.get("name") or a.get("product") or "Cuenta",
        type=a.get("cash_account_type", "CACC"),
        currency=a.get("currency", "EUR"),
        iban=acct_id.get("iban"),
        raw=a,
    )


def _amount(b: dict) -> float | None:
    v = b.get("balance_amount", {}).get("amount")
    return float(v) if v is not None else None


def to_balance(balances: list[dict]) -> Balance:
    available = current = None
    currency = "EUR"
    for b in balances:
        currency = b.get("balance_amount", {}).get("currency", currency)
        bt = b.get("balance_type")
        if bt in _AVAILABLE and available is None:
            available = _amount(b)
        if bt in _CURRENT and current is None:
            current = _amount(b)
    if balances and available is None and current is None:
        available = current = _amount(balances[0])
        currency = balances[0].get("balance_amount", {}).get("currency", currency)
    return Balance(
        available=available,
        current=current,
        currency=currency,
        snapshot_at=datetime.now(timezone.utc),
        raw={"balances": balances},
    )


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.strptime(value[:10], "%Y-%m-%d")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _description(raw: dict) -> str:
    ri = raw.get("remittance_information")
    if isinstance(ri, list) and ri:
        return " ".join(ri)
    if isinstance(ri, str):
        return ri
    return ""


def _provider_id(raw: dict) -> str:
    for k in ("entry_reference", "transaction_id"):
        if raw.get(k):
            return str(raw[k])
    basis = "|".join(
        str(x)
        for x in (
            raw.get("booking_date"),
            raw.get("transaction_amount", {}).get("amount"),
            _description(raw),
        )
    )
    return "eb_" + hashlib.sha1(basis.encode()).hexdigest()[:24]


def to_transaction(raw: dict) -> Transaction:
    indicator = str(raw.get("credit_debit_indicator", "")).upper()
    amount = float(raw.get("transaction_amount", {}).get("amount", 0.0))
    # El sentido lo marca credit_debit_indicator (DBIT/CRDT); el importe es positivo.
    side = "debit" if indicator == "DBIT" or amount < 0 else "credit"
    party = raw.get("creditor") if side == "debit" else raw.get("debtor")
    merchant = (party or {}).get("name")
    booked = (
        raw.get("booking_date")
        or raw.get("value_date")
        or raw.get("transaction_date")
    )
    return Transaction(
        provider_id=_provider_id(raw),
        amount=abs(amount),
        currency=raw.get("transaction_amount", {}).get("currency", "EUR"),
        booked_at=_parse_date(booked),
        description=_description(raw),
        type=side,
        merchant_name=merchant,
        provider_category=None,  # Enable Banking no aporta categoría
        raw=raw,
    )
