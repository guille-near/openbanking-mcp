from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from finmcp.db.models import Account, Base, Transaction


@pytest.fixture
def Session():
    """Factory de sesiones sobre una SQLite en memoria (compartida por test).

    StaticPool mantiene una única conexión, así varias sesiones ven la misma BD
    en memoria (necesario, p.ej., para el test del flujo de `run_sync`).
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture
def session(Session):
    with Session() as s:
        s.add(Account(id="acc1", name="Test", type="TRANSACTION", currency="EUR"))
        s.commit()
        yield s


@pytest.fixture
def make_tx(session):
    """Crea y persiste una transacción en la cuenta de prueba."""
    counter = {"n": 0}

    def _make(
        amount: float,
        *,
        type: str = "debit",
        merchant: str | None = None,
        description: str = "",
        booked_at: datetime | None = None,
        provider_category: str | None = None,
        my_category: str | None = None,
        currency: str = "EUR",
    ) -> Transaction:
        counter["n"] += 1
        tx = Transaction(
            id=f"tx{counter['n']}",
            account_id="acc1",
            amount=amount,
            currency=currency,
            booked_at=booked_at or datetime.now(timezone.utc),
            description=description,
            type=type,
            merchant_name=merchant,
            provider_category=provider_category,
            my_category=my_category,
        )
        session.add(tx)
        session.commit()
        return tx

    return _make
