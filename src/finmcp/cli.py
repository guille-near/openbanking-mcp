from __future__ import annotations

import typer

app = typer.Typer(
    help="Finanzas personales sobre TrueLayer (solo lectura)."
)
rules_app = typer.Typer(help="Reglas de categorización personalizadas.")
app.add_typer(rules_app, name="rules")


@app.command()
def auth() -> None:
    """Autoriza con el proveedor activo y guarda las credenciales cifradas."""
    from finmcp.config import settings

    prov = settings.provider.lower()
    if prov == "enablebanking":
        from finmcp.providers.enablebanking.auth import run_link_flow

        run_link_flow()
    elif prov == "gocardless":
        from finmcp.providers.gocardless.auth import run_link_flow

        run_link_flow()
    else:
        from finmcp.providers.truelayer.auth import run_authorization_flow

        run_authorization_flow()


@app.command()
def institutions(
    country: str = typer.Option(
        None, help="Código país ISO-3166 (p.ej. es). Por defecto, el del proveedor."
    ),
) -> None:
    """Lista las entidades del proveedor activo (para fijar el banco en .env)."""
    from finmcp.config import settings

    prov = settings.provider.lower()
    if prov == "enablebanking":
        from finmcp.providers.enablebanking.auth import list_aspsps

        code = country or settings.enablebanking_country
        rows = list_aspsps(code)
        if not rows:
            typer.echo(f"Sin entidades para el país '{code}'.")
            raise typer.Exit()
        for a in rows:
            typer.echo(f"{a.get('name', '')}  ·  {a.get('country', '')}")
        return

    from finmcp.providers.gocardless.auth import list_institutions

    code = country or settings.gocardless_country
    rows = list_institutions(code)
    if not rows:
        typer.echo(f"Sin entidades para el país '{code}'.")
        raise typer.Exit()
    for inst in rows:
        typer.echo(f"{inst['id']}  ·  {inst.get('name', '')}")


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


@rules_app.command("add")
def rules_add(
    pattern: str = typer.Argument(..., help="Subcadena a buscar (case-insensitive)"),
    category: str = typer.Argument(..., help="Categoría a asignar"),
    field: str = typer.Option("any", help="merchant | description | any"),
    priority: int = typer.Option(100, help="Menor = se evalúa antes"),
) -> None:
    """Añade una regla y la aplica a los movimientos existentes."""
    from finmcp.analytics.categorization import apply_rules
    from finmcp.db.models import CategoryRule
    from finmcp.db.session import SessionLocal, init_db

    init_db()
    with SessionLocal() as s:
        s.add(
            CategoryRule(
                pattern=pattern, category=category, field=field, priority=priority
            )
        )
        s.commit()
        changed = apply_rules(s)
    typer.echo(
        f"Regla añadida: '{pattern}' -> {category} · recategorizadas {changed} tx"
    )


@rules_app.command("list")
def rules_list() -> None:
    """Lista las reglas de categorización."""
    from finmcp.db.models import CategoryRule
    from finmcp.db.session import SessionLocal, init_db

    init_db()
    with SessionLocal() as s:
        rows = (
            s.query(CategoryRule)
            .order_by(CategoryRule.priority.asc(), CategoryRule.id.asc())
            .all()
        )
        if not rows:
            typer.echo("Sin reglas. Añade una con `finmcp rules add`.")
            raise typer.Exit()
        for r in rows:
            typer.echo(
                f"[{r.priority}] '{r.pattern}' ({r.field}) -> {r.category}  (id={r.id})"
            )


@app.command()
def categorize(
    only_new: bool = typer.Option(
        False, "--only-new", help="Solo las que aún no tienen categoría manual"
    ),
) -> None:
    """Reaplica las reglas de categorización a los movimientos."""
    from finmcp.analytics.categorization import apply_rules
    from finmcp.db.session import SessionLocal, init_db

    init_db()
    with SessionLocal() as s:
        changed = apply_rules(s, only_uncategorized=only_new)
    typer.echo(f"Recategorizadas {changed} transacciones.")


@app.command()
def serve(
    http: bool = typer.Option(
        False, "--http", help="Transporte HTTP (para ChatGPT); por defecto stdio"
    ),
    host: str = typer.Option("127.0.0.1", help="Host en modo --http"),
    port: int = typer.Option(8000, help="Puerto en modo --http"),
) -> None:
    """Arranca el servidor MCP (solo lectura).

    stdio para Claude Desktop/Cursor; --http para conectores remotos (ChatGPT).
    En --http, define FINMCP_HTTP_TOKEN para exigir bearer auth.
    """
    from finmcp.mcp.server import main

    main(http=http, host=host, port=port)


if __name__ == "__main__":
    app()
