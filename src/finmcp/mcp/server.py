from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from finmcp.analytics.anomalies import detect_unusual_charges
from finmcp.analytics.categories import category_of, spend_by_category
from finmcp.analytics.subscriptions import detect_subscriptions
from finmcp.analytics.summaries import monthly_summary
from finmcp.db import models, queries
from finmcp.db.session import SessionLocal, init_db
from finmcp.util import parse_date

mcp = FastMCP("openbanking-mcp")


def _tx_dict(t: models.Transaction) -> dict:
    return {
        "id": t.id,
        "account_id": t.account_id,
        "amount": t.amount,
        "currency": t.currency,
        "date": t.booked_at.date().isoformat(),
        "description": t.description,
        "type": t.type,
        "merchant": t.merchant_name,
        "category": category_of(t),
    }


@mcp.tool()
def list_accounts() -> list[dict]:
    """Lista las cuentas bancarias sincronizadas."""
    with SessionLocal() as s:
        return [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "currency": a.currency,
                "iban": a.iban,
            }
            for a in queries.list_accounts(s)
        ]


@mcp.tool()
def get_balances() -> list[dict]:
    """Saldo más reciente de cada cuenta."""
    with SessionLocal() as s:
        return [
            {
                "account_id": b.account_id,
                "available": b.available,
                "current": b.current,
                "currency": b.currency,
                "as_of": b.snapshot_at.isoformat(),
            }
            for b in queries.latest_balances(s)
        ]


@mcp.tool()
def get_transactions(
    account_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Movimientos filtrados por cuenta, fechas (YYYY-MM-DD) y tipo (debit/credit)."""
    with SessionLocal() as s:
        txs = queries.query_transactions(
            s,
            account_id=account_id,
            start=parse_date(start),
            end=parse_date(end),
            type=type,
            limit=limit,
        )
        return [_tx_dict(t) for t in txs]


@mcp.tool()
def search_transactions(query: str, limit: int = 50) -> list[dict]:
    """Busca movimientos por texto en el comercio o el concepto."""
    with SessionLocal() as s:
        txs = queries.query_transactions(s, text=query, limit=limit)
        return [_tx_dict(t) for t in txs]


@mcp.tool()
def spend_by_category_tool(
    start: str | None = None, end: str | None = None
) -> list[dict]:
    """Gasto agregado por categoría en un periodo (fechas YYYY-MM-DD)."""
    with SessionLocal() as s:
        return spend_by_category(s, parse_date(start), parse_date(end))


@mcp.tool()
def list_subscriptions(lookback_months: int = 6) -> list[dict]:
    """Cargos recurrentes detectados (suscripciones / domiciliaciones)."""
    with SessionLocal() as s:
        return detect_subscriptions(s, lookback_months=lookback_months)


@mcp.tool()
def unusual_charges(
    start: str | None = None, end: str | None = None
) -> list[dict]:
    """Cargos atípicos respecto al histórico de cada comercio."""
    with SessionLocal() as s:
        return detect_unusual_charges(s, parse_date(start), parse_date(end))


@mcp.tool()
def monthly_summary_tool(year: int, month: int) -> dict:
    """Resumen mensual: ingresos, gastos, neto, top comercios y categorías."""
    with SessionLocal() as s:
        return monthly_summary(s, year, month)


@mcp.tool()
def sync_status() -> dict:
    """Estado de la última sincronización."""
    with SessionLocal() as s:
        run = (
            s.query(models.SyncRun)
            .order_by(models.SyncRun.started_at.desc())
            .first()
        )
        if run is None:
            return {"status": "never", "detail": "Ejecuta `finmcp sync`."}
        return {
            "status": run.status,
            "started_at": run.started_at.isoformat(),
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "accounts_synced": run.accounts_synced,
            "tx_added": run.tx_added,
        }


def _wrap_bearer_auth(app, token: str):
    """Middleware mínimo: exige `Authorization: Bearer <token>` en cada petición."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class BearerAuth(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.headers.get("authorization", "") != f"Bearer {token}":
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    app.add_middleware(BearerAuth)
    return app


def main(http: bool = False, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Arranca el servidor MCP.

    - stdio (por defecto): para Claude Desktop / Cursor (proceso local).
    - http: transporte Streamable HTTP en /mcp para conectores remotos (ChatGPT).
      Si FINMCP_HTTP_TOKEN está definido, exige ese bearer token.
    """
    import os

    init_db()
    if not http:
        mcp.run()
        return

    import uvicorn

    app = mcp.streamable_http_app()
    token = os.environ.get("FINMCP_HTTP_TOKEN", "")
    if token:
        app = _wrap_bearer_auth(app, token)
    else:
        print(
            "AVISO: sin FINMCP_HTTP_TOKEN; el endpoint queda SIN autenticación. "
            "No lo expongas públicamente con datos bancarios."
        )
    mcp.settings.host, mcp.settings.port = host, port
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
