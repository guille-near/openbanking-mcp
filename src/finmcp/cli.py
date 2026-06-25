from __future__ import annotations

import typer

app = typer.Typer(
    help="Finanzas personales sobre TrueLayer (solo lectura)."
)


@app.command()
def auth() -> None:
    """Autoriza con TrueLayer (flujo OAuth) y guarda los tokens cifrados."""
    from finmcp.providers.truelayer.auth import run_authorization_flow

    run_authorization_flow()


@app.command()
def sync(
    from_date: str = typer.Option(None, "--from", help="Fecha inicio YYYY-MM-DD"),
    to_date: str = typer.Option(None, "--to", help="Fecha fin YYYY-MM-DD"),
) -> None:
    """Sincroniza cuentas, saldos y movimientos a la base de datos local."""
    from finmcp.sync.service import run_sync

    run = run_sync(from_date, to_date)
    typer.echo(
        f"Sync OK · cuentas: {run.accounts_synced} · nuevas tx: {run.tx_added}"
    )


@app.command()
def accounts() -> None:
    """Lista las cuentas almacenadas localmente."""
    from finmcp.db.models import Account
    from finmcp.db.session import SessionLocal, init_db

    init_db()
    with SessionLocal() as s:
        rows = s.query(Account).all()
        if not rows:
            typer.echo("No hay cuentas. Ejecuta `finmcp sync` primero.")
            raise typer.Exit()
        for a in rows:
            typer.echo(
                f"- {a.name} ({a.type}) · {a.currency} · {a.iban or 's/IBAN'}"
            )


@app.command()
def serve() -> None:
    """Arranca el servidor MCP (solo lectura) sobre stdio."""
    from finmcp.mcp.server import main

    main()


if __name__ == "__main__":
    app()
