from __future__ import annotations

from types import SimpleNamespace

from finmcp.analytics.categories import (
    UNCATEGORIZED,
    category_of,
    spend_by_category,
)


def test_category_of_precedence():
    # my_category gana sobre provider_category
    tx = SimpleNamespace(my_category="Supermercado", provider_category="Groceries")
    assert category_of(tx) == "Supermercado"
    # sin manual, usa la del proveedor
    tx = SimpleNamespace(my_category=None, provider_category="Groceries")
    assert category_of(tx) == "Groceries"
    # sin nada, "Sin categoría"
    tx = SimpleNamespace(my_category=None, provider_category=None)
    assert category_of(tx) == UNCATEGORIZED


def test_spend_by_category_aggregates_and_sorts(make_tx, session):
    make_tx(10.0, type="debit", provider_category="Comida")
    make_tx(15.0, type="debit", provider_category="Comida")
    make_tx(40.0, type="debit", provider_category="Ocio")
    make_tx(999.0, type="credit", provider_category="Nómina")  # ingreso: se ignora

    rows = spend_by_category(session)

    assert rows[0] == {"category": "Ocio", "total": 40.0, "count": 1}
    assert rows[1] == {"category": "Comida", "total": 25.0, "count": 2}
    assert all(r["category"] != "Nómina" for r in rows)
