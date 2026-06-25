from __future__ import annotations

import pytest

from finmcp.db.models import SyncRun
from finmcp.sync import service


def test_run_sync_marks_error_on_failure(monkeypatch, Session):
    """Si el pull al banco falla, el SyncRun queda 'error' (no colgado en 'running')."""
    monkeypatch.setattr(service, "init_db", lambda: None)
    monkeypatch.setattr(service, "SessionLocal", Session)

    class BoomClient:
        def get_accounts(self):
            raise RuntimeError("HTTP 401 token caducado")

    monkeypatch.setattr(service, "get_provider", lambda: BoomClient())

    with pytest.raises(RuntimeError):
        service.run_sync()

    with Session() as s:
        run = s.query(SyncRun).one()
        assert run.status == "error"
        assert run.finished_at is not None
        assert "401" in run.detail


def test_run_sync_ok_path(monkeypatch, Session):
    from finmcp.providers.types import Account, Transaction
    from datetime import datetime, timezone

    monkeypatch.setattr(service, "init_db", lambda: None)
    monkeypatch.setattr(service, "SessionLocal", Session)

    class FakeClient:
        def get_accounts(self):
            return [Account(provider_account_id="a1", name="C", type="T", currency="EUR")]

        def get_balance(self, account_id):
            raise RuntimeError("sin saldo")  # no debe romper el sync

        def get_transactions(self, account_id, from_date=None, to_date=None):
            return [
                Transaction(
                    provider_id="t1",
                    amount=10.0,
                    currency="EUR",
                    booked_at=datetime.now(timezone.utc),
                    description="x",
                    type="debit",
                )
            ]

    monkeypatch.setattr(service, "get_provider", lambda: FakeClient())

    run = service.run_sync()
    assert run.status == "ok"
    assert run.accounts_synced == 1
    assert run.tx_added == 1
