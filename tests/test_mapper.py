from __future__ import annotations

from finmcp.providers.truelayer import mapper


def test_to_transaction_debit_by_type():
    tx = mapper.to_transaction(
        {
            "transaction_id": "t1",
            "amount": 12.5,
            "currency": "EUR",
            "timestamp": "2026-01-10T09:00:00Z",
            "description": "MERCADONA",
            "transaction_type": "DEBIT",
            "merchant_name": "Mercadona",
            "transaction_classification": ["Food & Dining", "Groceries"],
        }
    )
    assert tx.type == "debit"
    assert tx.amount == 12.5
    assert tx.provider_category == "Food & Dining"
    assert tx.merchant_name == "Mercadona"


def test_to_transaction_debit_by_negative_sign():
    tx = mapper.to_transaction(
        {"transaction_id": "t2", "amount": -30.0, "transaction_type": ""}
    )
    assert tx.type == "debit"
    assert tx.amount == 30.0  # siempre positivo; el signo va en type


def test_to_transaction_credit():
    tx = mapper.to_transaction(
        {"transaction_id": "t3", "amount": 100.0, "transaction_type": "CREDIT"}
    )
    assert tx.type == "credit"
    assert tx.amount == 100.0


def test_to_transaction_no_classification():
    tx = mapper.to_transaction(
        {"transaction_id": "t4", "amount": 5.0, "transaction_type": "DEBIT"}
    )
    assert tx.provider_category is None


def test_to_account_display_name_fallback():
    acc = mapper.to_account(
        {"account_id": "a1", "account_type": "TRANSACTION", "currency": "EUR"}
    )
    assert acc.provider_account_id == "a1"
    assert acc.name == "TRANSACTION"  # cae al account_type si no hay display_name
    assert acc.iban is None


def test_to_balance_parses_timestamp():
    bal = mapper.to_balance(
        {
            "available": 1000.0,
            "current": 950.0,
            "currency": "EUR",
            "update_timestamp": "2026-01-10T09:00:00Z",
        }
    )
    assert bal.available == 1000.0
    assert bal.snapshot_at.year == 2026
