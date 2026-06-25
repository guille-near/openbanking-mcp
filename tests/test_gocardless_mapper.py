from __future__ import annotations

from finmcp.providers.gocardless import mapper


def test_to_transaction_debit_negative_amount():
    tx = mapper.to_transaction(
        {
            "transactionId": "g1",
            "bookingDate": "2026-01-10",
            "transactionAmount": {"amount": "-12.50", "currency": "EUR"},
            "creditorName": "Mercadona",
            "remittanceInformationUnstructured": "COMPRA MERCADONA",
        }
    )
    assert tx.type == "debit"
    assert tx.amount == 12.5
    assert tx.merchant_name == "Mercadona"  # acreedor en un cargo
    assert tx.description == "COMPRA MERCADONA"
    assert tx.provider_category is None
    assert tx.booked_at.year == 2026


def test_to_transaction_credit_uses_debtor():
    tx = mapper.to_transaction(
        {
            "transactionId": "g2",
            "bookingDate": "2026-01-01",
            "transactionAmount": {"amount": "2000.00", "currency": "EUR"},
            "debtorName": "ACME Payroll",
        }
    )
    assert tx.type == "credit"
    assert tx.amount == 2000.0
    assert tx.merchant_name == "ACME Payroll"  # ordenante en un ingreso


def test_to_transaction_description_array_fallback():
    tx = mapper.to_transaction(
        {
            "transactionId": "g3",
            "transactionAmount": {"amount": "-5.0", "currency": "EUR"},
            "remittanceInformationUnstructuredArray": ["PAGO", "TARJETA"],
        }
    )
    assert tx.description == "PAGO TARJETA"


def test_provider_id_stable_hash_when_no_id():
    raw = {
        "bookingDate": "2026-01-10",
        "transactionAmount": {"amount": "-9.99", "currency": "EUR"},
        "remittanceInformationUnstructured": "NETFLIX",
    }
    a = mapper.to_transaction(raw).provider_id
    b = mapper.to_transaction(dict(raw)).provider_id
    assert a == b  # determinista -> idempotencia del upsert
    assert a.startswith("gc_")


def test_provider_id_prefers_internal_when_no_transaction_id():
    tx = mapper.to_transaction(
        {
            "internalTransactionId": "INT-123",
            "transactionAmount": {"amount": "-1.0", "currency": "EUR"},
        }
    )
    assert tx.provider_id == "INT-123"


def test_to_balance_picks_available_and_current():
    bal = mapper.to_balance(
        [
            {"balanceAmount": {"amount": "100.00", "currency": "EUR"}, "balanceType": "interimAvailable"},
            {"balanceAmount": {"amount": "120.00", "currency": "EUR"}, "balanceType": "closingBooked"},
        ]
    )
    assert bal.available == 100.0
    assert bal.current == 120.0
    assert bal.currency == "EUR"


def test_to_balance_single_unknown_type_used_for_both():
    bal = mapper.to_balance(
        [{"balanceAmount": {"amount": "50.00", "currency": "EUR"}, "balanceType": "nonInvoiced"}]
    )
    assert bal.available == 50.0
    assert bal.current == 50.0


def test_to_account_prefers_details_name_and_iban():
    acc = mapper.to_account(
        "acc-1",
        {"owner_name": "Guille", "iban": "ES00META"},
        {"name": "Cuenta Nómina", "iban": "ES99DETAILS", "currency": "EUR"},
    )
    assert acc.provider_account_id == "acc-1"
    assert acc.name == "Cuenta Nómina"
    assert acc.iban == "ES99DETAILS"
    assert acc.currency == "EUR"
