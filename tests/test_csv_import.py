from __future__ import annotations

from finmcp.importers.csv_import import (
    import_transactions,
    parse_amount,
    parse_date,
    parse_rows,
)


def test_parse_amount_spanish_and_english():
    assert parse_amount("1.234,56") == 1234.56
    assert parse_amount("-45,00") == -45.0
    assert parse_amount("1234.56") == 1234.56
    assert parse_amount("12,50 €") == 12.5
    assert parse_amount("") is None
    assert parse_amount("n/a") is None


def test_parse_date_formats():
    assert parse_date("28/03/2026").day == 28
    assert parse_date("2026-03-28").month == 3
    assert parse_date("28.03.2026").year == 2026
    assert parse_date("") is None
    assert parse_date("no-fecha") is None


SAMPLE = """Movimientos de la cuenta ES58...
Algún preámbulo del banco

Fecha;Concepto;Importe;Saldo
28/03/2026;COMPRA MERCADONA;-23,45;1.000,00
27/03/2026;NOMINA EMPRESA SL;1.800,00;1.023,45
26/03/2026;RECIBO VODAFONE;-39,90;-776,55
;FILA SIN FECHA;-1,00;0
"""


def test_parse_rows_detects_header_and_parses():
    rows = parse_rows(SAMPLE)
    # 3 filas válidas (la de sin fecha se descarta)
    assert len(rows) == 3
    assert rows[0]["amount"] == -23.45
    assert rows[0]["description"] == "COMPRA MERCADONA"
    assert rows[1]["amount"] == 1800.0
    assert rows[0]["date"].day == 28


def test_parse_rows_comma_delimiter():
    text = "Fecha,Concepto,Importe\n01/01/2026,PAGO,-10.00\n"
    rows = parse_rows(text)
    assert len(rows) == 1 and rows[0]["amount"] == -10.0


def test_import_transactions_inserts_and_dedups(session):
    from finmcp.db.models import Account, Transaction

    acc = session.get(Account, "acc1")
    rows = parse_rows(SAMPLE)

    added, skipped = import_transactions(session, acc, rows)
    assert added == 3 and skipped == 0

    txs = session.query(Transaction).all()
    assert len(txs) == 3
    # signo -> tipo, importe siempre positivo
    merc = next(t for t in txs if "MERCADONA" in t.description)
    assert merc.type == "debit" and merc.amount == 23.45
    nom = next(t for t in txs if "NOMINA" in t.description)
    assert nom.type == "credit" and nom.amount == 1800.0

    # Reimportar no duplica
    added2, skipped2 = import_transactions(session, acc, rows)
    assert added2 == 0 and skipped2 == 3
    assert session.query(Transaction).count() == 3


def test_import_dedups_against_existing_api_tx(session, make_tx):
    from datetime import datetime, timezone

    from finmcp.db.models import Account, Transaction

    # Movimiento ya traído por la API: mismo día, importe y tipo
    make_tx(
        23.45,
        type="debit",
        merchant="Mercadona",
        booked_at=datetime(2026, 3, 28, tzinfo=timezone.utc),
    )
    acc = session.get(Account, "acc1")
    rows = parse_rows(SAMPLE)

    added, skipped = import_transactions(session, acc, rows)
    # La de Mercadona (28/03, -23,45) se salta por dedup; entran las otras 2
    assert added == 2 and skipped == 1
    assert session.query(Transaction).count() == 3
