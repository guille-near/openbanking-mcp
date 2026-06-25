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


def test_parse_xlsx(tmp_path):
    from datetime import datetime

    from openpyxl import Workbook

    from finmcp.importers.csv_import import parse_xlsx

    wb = Workbook()
    ws = wb.active
    ws.append(["Movimientos de la cuenta ES58..."])  # preámbulo
    ws.append([])
    ws.append(["Fecha", "Concepto", "Importe", "Saldo"])
    ws.append([datetime(2026, 3, 28), "COMPRA MERCADONA", -23.45, 1000.0])
    ws.append([datetime(2026, 3, 27), "NOMINA EMPRESA SL", 1800.0, 1023.45])
    p = tmp_path / "mov.xlsx"
    wb.save(p)

    rows = parse_xlsx(str(p))
    assert len(rows) == 2
    assert rows[0]["amount"] == -23.45
    assert rows[0]["description"] == "COMPRA MERCADONA"
    assert rows[0]["date"].day == 28
    assert rows[1]["amount"] == 1800.0


def test_import_transactions_inserts_and_dedups(session):
    from finmcp.db.models import Account, Transaction

    acc = session.get(Account, "acc1")
    rows = parse_rows(SAMPLE)

    added, skipped = import_transactions(session, rows, account=acc)
    assert added == 3 and skipped == 0

    txs = session.query(Transaction).all()
    assert len(txs) == 3
    # signo -> tipo, importe siempre positivo
    merc = next(t for t in txs if "MERCADONA" in t.description)
    assert merc.type == "debit" and merc.amount == 23.45
    nom = next(t for t in txs if "NOMINA" in t.description)
    assert nom.type == "credit" and nom.amount == 1800.0

    # Reimportar no duplica
    added2, skipped2 = import_transactions(session, rows, account=acc)
    assert added2 == 0 and skipped2 == 3
    assert session.query(Transaction).count() == 3


# Formato real de CaixaBank: Ingreso/Gasto separados, nº de cuenta y "Concepto
# complementario 1" con el comercio. (Tabla cruda como la que produce parse_xls.)
CAIXA_TABLE = [
    [""] * 13,
    ["", "MOVIMIENTOS DESDE : 01/01/2025"] + [""] * 11,
    [""] * 13,
    ["", "Número de cuenta", "Oficina", "Divisa", "F. Operación", "F. Valor",
     "Ingreso (+)", "Gasto (-)", "Saldo (+)", "Saldo (-)", "Concepto común",
     "Concepto propio", "Concepto complementario 1"],
    ["", "2100 8931 10 1300320553", "9736", "EUR", "25/06/2026", "25/06/2026",
     "", "0.75", "122.46", "", "12", "040", "EL CORTE INGLES T"],
    ["", "2100 8931 10 1300320553", "9736", "EUR", "09/06/2026", "09/06/2026",
     "50.0", "", "244.69", "", "02", "040", "PRIO E MOBILITY"],
    ["", "2100 8931 11 1300405400", "9736", "EUR", "01/06/2026", "01/06/2026",
     "", "34.0", "100.00", "", "12", "040", "MERCADONA STA.MAR"],
]


def test_rows_from_table_caixabank_ingreso_gasto():
    from finmcp.importers.csv_import import _rows_from_table

    rows = _rows_from_table(CAIXA_TABLE)
    assert len(rows) == 3
    assert rows[0]["amount"] == -0.75  # gasto -> negativo
    assert rows[0]["description"] == "EL CORTE INGLES T"
    assert "1300320553" in rows[0]["account"]
    assert rows[1]["amount"] == 50.0  # ingreso -> positivo


def test_import_multi_account_maps_by_number(Session):
    from finmcp.db.models import Account, Transaction
    from finmcp.importers.csv_import import _rows_from_table, import_transactions

    with Session() as s:
        s.add(Account(id="a58", name="C1", type="CACC", currency="EUR",
                      iban="ES5821008931101300320553"))
        s.add(Account(id="a73", name="C2", type="CACC", currency="EUR",
                      iban="ES7321008931111300405400"))
        s.commit()

        rows = _rows_from_table(CAIXA_TABLE)
        added, skipped = import_transactions(s, rows)  # sin cuenta por defecto
        assert added == 3
        assert s.query(Transaction).filter_by(account_id="a58").count() == 2
        assert s.query(Transaction).filter_by(account_id="a73").count() == 1


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

    added, skipped = import_transactions(session, rows, account=acc)
    # La de Mercadona (28/03, -23,45) se salta por dedup; entran las otras 2
    assert added == 2 and skipped == 1
    assert session.query(Transaction).count() == 3
