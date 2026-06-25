# caixa-mcp

Servidor MCP de **finanzas personales de solo lectura** sobre la **TrueLayer Data API** (PSD2).
Consulta cuentas, saldos y movimientos de bancos españoles (CaixaBank) y genera analítica:
gasto por categoría, suscripciones, cargos inusuales y resúmenes mensuales.

> **Solo lectura.** No inicia pagos ni transferencias. Los scopes solicitados a TrueLayer
> son exclusivamente de datos (`info accounts balance transactions ...`).

## Arquitectura

```txt
CaixaBank (PSD2)
   -> Proveedor Open Banking (TrueLayer / GoCardless)  [interfaz BankDataProvider]
   -> Capa de sincronización (pull idempotente e incremental)
   -> SQLite (SQLAlchemy)
   -> Capa de analítica (funciones puras)
   -> Servidor MCP (solo lectura)
   -> Cliente MCP: Claude Desktop / Cursor
```

El servidor MCP **lee de SQLite, nunca llama al banco en caliente**. La sincronización
es un proceso aparte (`finmcp sync`, manual o por cron).

## Puesta en marcha

```bash
# 1. Entorno
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configura credenciales (sandbox)
cp .env.example .env
#   -> rellena TRUELAYER_CLIENT_ID y TRUELAYER_CLIENT_SECRET desde console.truelayer.com
#   -> registra la redirect URI http://localhost:3000/callback en tu app

# 3. Autoriza (abre el navegador, Mock Bank en sandbox)
finmcp auth

# 4. Sincroniza datos a SQLite
finmcp sync

# 5. Revisa
finmcp accounts
```

## Comandos

| Comando | Estado | Descripción |
|---|---|---|
| `finmcp auth` | ✅ | Flujo OAuth, guarda tokens cifrados |
| `finmcp sync` | ✅ | Trae cuentas/saldos/movimientos a SQLite |
| `finmcp accounts` | ✅ | Lista cuentas locales |
| `finmcp serve` | ✅ | Arranca el servidor MCP (stdio) |

## Herramientas MCP (solo lectura)

`list_accounts` · `get_balances` · `get_transactions` · `search_transactions` ·
`spend_by_category_tool` · `list_subscriptions` · `unusual_charges` ·
`monthly_summary_tool` · `sync_status`

> Cargos inusuales usa **mediana + MAD** (robusto): un único pico no contamina
> su propia línea base, así que se detecta de verdad.

## Conectar a Claude Desktop

En `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "caixa": {
      "command": "/Users/iyorica/caixa-mcp/.venv/bin/finmcp",
      "args": ["serve"]
    }
  }
}
```

El servidor lee de SQLite; recuerda correr `finmcp sync` (manual o por cron) para
mantener los datos al día.

## Notas PSD2

- El `access_token` dura ~1 h; se refresca solo con el `refresh_token`.
- PSD2 obliga a **re-consentir con SCA cada 90 días**: pasado ese plazo hay que repetir `finmcp auth`.
- **CaixaBank real solo existe en `live`.** En `sandbox` se usa el Mock Bank de TrueLayer.
