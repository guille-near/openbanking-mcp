from __future__ import annotations

from finmcp.providers.enablebanking import mapper


def test_to_transaction_debit_by_indicator():
    tx = mapper.to_transaction(
        {
            "entry_reference": "e1",
            "booking_date": "2026-01-10",
            "transaction_amount": {"amount": "12.50", "currency": "EUR"},
            "credit_debit_indicator": "DBIT",
            "creditor": {"name": "Mercadona"},
            "remittance_information": ["COMPRA MERCADONA"],
        }
    )
    assert tx.type == "debit"
    assert tx.amount == 12.5  # importe positivo; el sentido va en el indicador
    assert tx.merchant_name == "Mercadona"
    assert tx.description == "COMPRA MERCADONA"
    assert tx.provider_id == "e1"
    assert tx.booked_at.year == 2026


def test_to_transaction_credit_uses_debtor():
    tx = mapper.to_transaction(
        {
            "entry_reference": "e2",
            "booking_date": "2026-01-01",
            "transaction_amount": {"amount": "2000.00", "currency": "EUR"},
            "credit_debit_indicator": "CRDT",
            "debtor": {"name": "ACME Payroll"},
        }
    )
    assert tx.type == "credit"
    assert tx.amount == 2000.0
    assert tx.merchant_name == "ACME Payroll"


def test_to_transaction_remittance_string():
    tx = mapper.to_transaction(
        {
            "entry_reference": "e3",
            "transaction_amount": {"amount": "5.0", "currency": "EUR"},
            "credit_debit_indicator": "DBIT",
            "remittance_information": "PAGO TARJETA",
        }
    )
    assert tx.description == "PAGO TARJETA"


def test_provider_id_hash_when_no_reference():
    raw = {
        "booking_date": "2026-01-10",
        "transaction_amount": {"amount": "9.99", "currency": "EUR"},
        "credit_debit_indicator": "DBIT",
        "remittance_information": ["NETFLIX"],
    }
    a = mapper.to_transaction(raw).provider_id
    b = mapper.to_transaction(dict(raw)).provider_id
    assert a == b and a.startswith("eb_")


def test_to_balance_berlin_group_codes():
    bal = mapper.to_balance(
        [
            {"balance_amount": {"amount": "100.00", "currency": "EUR"}, "balance_type": "ITAV"},
            {"balance_amount": {"amount": "120.00", "currency": "EUR"}, "balance_type": "CLBD"},
        ]
    )
    assert bal.available == 100.0
    assert bal.current == 120.0


def test_to_account_uses_uid_and_iban():
    acc = mapper.to_account(
        {
            "uid": "uid-123",
            "account_id": {"iban": "ES99..."},
            "name": "Cuenta Nómina",
            "currency": "EUR",
            "cash_account_type": "CACC",
        }
    )
    assert acc.provider_account_id == "uid-123"
    assert acc.iban == "ES99..."
    assert acc.name == "Cuenta Nómina"
