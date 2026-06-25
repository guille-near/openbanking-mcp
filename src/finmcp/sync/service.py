from __future__ import annotations

from datetime import datetime, timezone

from finmcp.analytics.categorization import apply_rules
from finmcp.db import repo
from finmcp.db.models import SyncRun
from finmcp.db.session import SessionLocal, init_db
from finmcp.providers.truelayer.client import TrueLayerClient


def run_sync(
    from_date: str | None = None, to_date: str | None = None
) -> SyncRun:
    """Pull idempotente de cuentas, saldos y movimientos a SQLite."""
    init_db()
    client = TrueLayerClient()
    with SessionLocal() as session:
        # Persistimos el inicio antes de tocar el banco: así, si el pull falla,
        # la fila sobrevive al rollback y podemos marcarla como "error".
        run = SyncRun(started_at=datetime.now(timezone.utc), status="running")
        session.add(run)
        session.commit()

        try:
            tx_added = 0
            accounts = client.get_accounts()
            for acc in accounts:
                repo.upsert_account(session, acc)
                try:
                    bal = client.get_balance(acc.provider_account_id)
                    repo.add_balance(session, acc.provider_account_id, bal)
                except Exception:  # noqa: BLE001 -- el saldo no debe romper el sync
                    pass
                for tx in client.get_transactions(
                    acc.provider_account_id, from_date, to_date
                ):
                    if repo.upsert_transaction(session, acc.provider_account_id, tx):
                        tx_added += 1

            run.accounts_synced = len(accounts)
            run.tx_added = tx_added
            run.finished_at = datetime.now(timezone.utc)
            run.status = "ok"
            session.commit()
            # Recategoriza según las reglas del usuario tras incorporar lo nuevo.
            apply_rules(session)
            session.refresh(run)
            return run
        except Exception as exc:  # noqa: BLE001 -- registramos y re-lanzamos
            session.rollback()
            run = session.get(SyncRun, run.id)
            run.status = "error"
            run.finished_at = datetime.now(timezone.utc)
            run.detail = str(exc)[:500]
            session.commit()
            raise
