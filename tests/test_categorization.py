from __future__ import annotations

from finmcp.analytics.categorization import apply_rules
from finmcp.db.models import CategoryRule, Transaction


def _by_merchant(session) -> dict[str, str | None]:
    return {t.merchant_name: t.my_category for t in session.query(Transaction).all()}


def test_apply_rules_assigns_and_counts(make_tx, session):
    make_tx(10.0, merchant="Mercadona", description="compra")
    make_tx(20.0, merchant="Netflix", description="suscripcion")
    make_tx(5.0, merchant="Bar Pepe", description="cañas")

    session.add(CategoryRule(pattern="mercadona", category="Supermercado", field="any"))
    session.add(CategoryRule(pattern="netflix", category="Ocio", field="merchant"))
    session.commit()

    changed = apply_rules(session)

    assert changed == 2  # Bar Pepe no casa ninguna regla
    cats = _by_merchant(session)
    assert cats["Mercadona"] == "Supermercado"
    assert cats["Netflix"] == "Ocio"
    assert cats["Bar Pepe"] is None


def test_apply_rules_priority_lower_wins(make_tx, session):
    make_tx(10.0, merchant="Amazon Prime")

    # priority menor (5) debe ganar a la mayor (100)
    session.add(CategoryRule(pattern="amazon", category="Compras", priority=100))
    session.add(CategoryRule(pattern="prime", category="Streaming", priority=5))
    session.commit()

    apply_rules(session)

    tx = session.query(Transaction).one()
    assert tx.my_category == "Streaming"


def test_apply_rules_field_merchant_ignores_description(make_tx, session):
    make_tx(10.0, merchant="Pepe", description="netflix factura")
    session.add(CategoryRule(pattern="netflix", category="Ocio", field="merchant"))
    session.commit()

    changed = apply_rules(session)

    assert changed == 0  # "netflix" está en la descripción, no en el comercio


def test_apply_rules_no_rules_returns_zero(make_tx, session):
    make_tx(10.0, merchant="Mercadona")
    assert apply_rules(session) == 0
