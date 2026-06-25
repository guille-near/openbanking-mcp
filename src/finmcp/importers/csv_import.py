from __future__ import annotations

import csv
import hashlib
import io
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from finmcp.db import models

# Heurística de cabeceras (CaixaBank y exports comunes, en ES/EN).
_DATE_KEYS = (
    "fecha valor",
    "fecha contable",
    "fecha operacion",
    "fecha operación",
    "f. operativa",
    "f.operativa",
    "fecha",
    "date",
)
_DESC_KEYS = (
    "concepto",
    "descripcion",
    "descripción",
    "detalle",
    "movimiento",
    "concept",
    "description",
)
_AMOUNT_KEYS = ("importe", "amount", "cantidad", "import")


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def parse_amount(raw: str) -> float | None:
    """Convierte un importe en formato español o inglés a float.

    '1.234,56' -> 1234.56 · '-45,00' -> -45.0 · '1234.56' -> 1234.56
    """
    s = (raw or "").strip().replace("€", "").replace(" ", "").replace("\xa0", "")
    if not s:
        return None
    if "," in s and "." in s:  # formato ES: punto miles, coma decimal
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:  # solo coma -> decimal
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _find_col(headers: list[str], keys: tuple[str, ...]) -> int | None:
    norm = [_norm(h) for h in headers]
    for key in keys:  # claves más específicas primero
        for i, h in enumerate(norm):
            if key in h:
                return i
    return None


def parse_rows(text: str, delimiter: str | None = None) -> list[dict]:
    """Extrae filas {date, amount, description} de un CSV de movimientos.

    Detecta el delimitador y la fila de cabecera (saltando preámbulos), y
    localiza por nombre las columnas de fecha, concepto e importe.
    """
    text = text.lstrip("﻿")  # quitar BOM
    if delimiter is None:
        sample = text.splitlines()[0] if text.strip() else ""
        delimiter = ";" if sample.count(";") >= sample.count(",") else ","

    table = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter)]
    return _rows_from_table(table)


def _cell_to_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def parse_xlsx(path: str) -> list[dict]:
    """Extrae filas {date, amount, description} de un Excel (.xlsx)."""
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    table = [
        [_cell_to_str(c) for c in row]
        for row in ws.iter_rows(values_only=True)
    ]
    return _rows_from_table(table)


def _rows_from_table(table: list[list[str]]) -> list[dict]:
    """Localiza la cabecera (saltando preámbulos) y extrae las filas válidas."""
    header_idx = None
    for i, row in enumerate(table):
        if (
            _find_col(row, _DATE_KEYS) is not None
            and _find_col(row, _AMOUNT_KEYS) is not None
        ):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(
            "No encuentro las cabeceras (fecha/importe) en el fichero. "
            "Revisa el formato o el delimitador (--delimiter)."
        )

    headers = table[header_idx]
    di = _find_col(headers, _DATE_KEYS)
    ci = _find_col(headers, _DESC_KEYS)
    ai = _find_col(headers, _AMOUNT_KEYS)

    out: list[dict] = []
    for row in table[header_idx + 1 :]:
        if not row or len(row) <= max(di, ai):
            continue
        d = parse_date(row[di])
        a = parse_amount(row[ai])
        if d is None or a is None:
            continue
        desc = row[ci].strip() if (ci is not None and ci < len(row)) else ""
        out.append({"date": d, "amount": a, "description": desc})
    return out


def import_transactions(
    session: Session, account: models.Account, rows: list[dict]
) -> tuple[int, int]:
    """Inserta filas como movimientos, deduplicando contra lo ya existente.

    Dedup por (cuenta, día, importe, tipo): si ya hay un movimiento igual
    (p.ej. traído por la API en la ventana de 90 días), se salta. Devuelve
    (importadas, saltadas).
    """
    existing = (
        session.query(models.Transaction)
        .filter(models.Transaction.account_id == account.id)
        .all()
    )
    seen = {
        (t.booked_at.date().isoformat(), round(t.amount, 2), t.type)
        for t in existing
    }

    added = skipped = 0
    for r in rows:
        side = "debit" if r["amount"] < 0 else "credit"
        amount = abs(r["amount"])
        key = (r["date"].date().isoformat(), round(amount, 2), side)
        if key in seen:
            skipped += 1
            continue
        tid = "csv_" + hashlib.sha1(
            f"{account.id}|{key}|{r['description']}".encode()
        ).hexdigest()[:24]
        if session.get(models.Transaction, tid) is not None:
            skipped += 1
            continue
        session.add(
            models.Transaction(
                id=tid,
                account_id=account.id,
                amount=amount,
                currency=account.currency,
                booked_at=r["date"],
                description=r["description"],
                type=side,
                merchant_name=None,
                provider_category=None,
                raw_json={"source": "csv"},
            )
        )
        seen.add(key)
        added += 1
    session.commit()
    return added, skipped
