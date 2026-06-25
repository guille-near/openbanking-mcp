from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from finmcp.providers.types import Account, Balance, Transaction

# GoCardless devuelve varios tipos de saldo; los agrupamos en "disponible"/"actual".
_AVAILABLE = {"interimAvailable", "forwardAvailable"}
_CURRENT = {"closingBooked", "interimBooked", "expected", "openingBooked"}


def to_account(account_id: str, meta: dict, details: dict) -> Account:
    name = (
        details.get("name")
        or details.get("product")
        or details.get("ownerName")
        or meta.get("owner_name")
        or "Cuenta"
    )
    return Account(
        provider_account_id=account_id,
        name=name,
        type=details.get("cashAccountType", "CACC"),
        currency=details.get("currency") or meta.get("currency") or "EUR",
        iban=details.get("iban") or meta.get("iban"),
        raw={"meta": meta, "details": details},
    )


def _amount(b: dict) -> float | None:
    amt = b.get("balanceAmount", {}).get("amount")
    return float(amt) if amt is not None else None


def to_balance(balances: list[dict]) -> Balance:
    available = current = None
    currency = "EUR"
    for b in balances:
        currency = b.get("balanceAmount", {}).get("currency", currency)
        bt = b.get("balanceType")
        if bt in _AVAILABLE and available is None:
            available = _amount(b)
        if bt in _CURRENT and current is None:
            current = _amount(b)
    # Si el banco solo expone un saldo sin tipo reconocido, úsalo para ambos.
    if balances and available is None and current is None:
        available = current = _amount(balances[0])
        currency = balances[0].get("balanceAmount", {}).get("currency", currency)
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


def _provider_id(raw: dict) -> str:
    for k in ("transactionId", "internalTransactionId"):
        if raw.get(k):
            return str(raw[k])
    # Último recurso: id estable derivado de los campos clave (idempotencia del upsert).
    basis = "|".join(
        str(x)
        for x in (
            raw.get("bookingDate"),
            raw.get("transactionAmount", {}).get("amount"),
            raw.get("remittanceInformationUnstructured"),
        )
    )
    return "gc_" + hashlib.sha1(basis.encode()).hexdigest()[:24]


def _description(raw: dict) -> str:
    if raw.get("remittanceInformationUnstructured"):
        return raw["remittanceInformationUnstructured"]
    arr = raw.get("remittanceInformationUnstructuredArray")
    if arr:
        return " ".join(arr)
    return ""


def to_transaction(raw: dict) -> Transaction:
    amount = float(raw.get("transactionAmount", {}).get("amount", 0.0))
    side = "debit" if amount < 0 else "credit"
    # En un cargo el contrapartida es el acreedor; en un ingreso, el ordenante.
    merchant = raw.get("creditorName") if side == "debit" else raw.get("debtorName")
    booked = (
        raw.get("bookingDate")
        or raw.get("bookingDateTime")
        or raw.get("valueDate")
    )
    return Transaction(
        provider_id=_provider_id(raw),
        amount=abs(amount),
        currency=raw.get("transactionAmount", {}).get("currency", "EUR"),
        booked_at=_parse_date(booked),
        description=_description(raw),
        type=side,
        merchant_name=merchant,
        provider_category=None,  # GoCardless no aporta categoría
        raw=raw,
    )
