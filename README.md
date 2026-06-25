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

## Conectar a ChatGPT

ChatGPT **no lanza procesos locales**: solo se conecta a servidores MCP **remotos
por HTTP(S)**. Hace falta exponer el servidor por una URL pública y añadirlo como
*connector* en **Modo Desarrollador** (Settings → Connectors, requiere plan de pago).

> ⚠️ **Datos bancarios por una URL pública.** Usa SIEMPRE bearer token y un túnel
> con HTTPS. Para uso solo-local, Claude Desktop (stdio) es más seguro.

```bash
# 1. Arranca en HTTP con token
export FINMCP_HTTP_TOKEN="<token-largo-aleatorio>"
finmcp serve --http --port 8000        # expone POST /mcp

# 2. Túnel HTTPS público (ejemplo con ngrok)
ngrok http 8000                         # -> https://xxxx.ngrok.app
```

En ChatGPT → Connectors → *Add custom connector*:
- **URL**: `https://xxxx.ngrok.app/mcp`
- **Auth**: cabecera `Authorization: Bearer <FINMCP_HTTP_TOKEN>`

El servidor responde `401` a cualquier petición sin el token correcto.

## Categorías personalizadas

```bash
finmcp rules add "mercadona" "Supermercado"
finmcp rules add "netflix" "Entretenimiento" --field merchant
finmcp rules list
finmcp categorize            # reaplica todas las reglas
```

Las reglas se reaplican automáticamente al final de cada `finmcp sync`.
`my_category` (manual/regla) tiene prioridad sobre la categoría del proveedor.

## Sincronización programada (macOS / launchd)

```bash
# Copia el LaunchAgent y actívalo (sync cada 6 h)
cp deploy/com.flowtheapp.caixa-mcp.sync.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.flowtheapp.caixa-mcp.sync.plist

# Logs en data/sync.log · para parar:
launchctl unload ~/Library/LaunchAgents/com.flowtheapp.caixa-mcp.sync.plist
```

## Notas PSD2

- El `access_token` dura ~1 h; se refresca solo con el `refresh_token`.
- PSD2 obliga a **re-consentir con SCA cada 90 días**: pasado ese plazo hay que repetir `finmcp auth`.
- **CaixaBank real solo existe en `live`.** En `sandbox` se usa el Mock Bank de TrueLayer.
