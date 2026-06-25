# openbanking-mcp

Servidor MCP de **finanzas personales de solo lectura** sobre la **TrueLayer Data API** (PSD2).
Consulta cuentas, saldos y movimientos de tus bancos y genera analítica: gasto por
categoría, suscripciones, cargos inusuales y resúmenes mensuales.

> **Solo lectura.** No inicia pagos ni transferencias. Los scopes solicitados a TrueLayer
> son exclusivamente de datos (`info accounts balance transactions ...`).

> **Funciona con cualquier banco que cubra TrueLayer** (cientos en UK y Europa). No está
> atado a ningún banco concreto: el banco se elige con `TRUELAYER_PROVIDERS` en tu `.env`.

## Aviso

Proyecto independiente, **no afiliado ni respaldado por TrueLayer ni por ningún banco**.
Manejas **tus propios datos bancarios** bajo tu responsabilidad: cada quien autohospeda
con sus credenciales, los datos nunca salen de tu máquina. Software entregado "tal cual",
sin garantías (ver [LICENSE](LICENSE)). Lee también las [notas PSD2](#notas-psd2).

## Arquitectura

```txt
Tu banco (PSD2)
   -> Proveedor Open Banking (TrueLayer)  [interfaz BankDataProvider]
   -> Capa de sincronización (pull idempotente e incremental)
   -> SQLite (SQLAlchemy)
   -> Capa de analítica (funciones puras)
   -> Servidor MCP (solo lectura)
   -> Cliente MCP: Claude Desktop / Cursor / ChatGPT
```

El servidor MCP **lee de SQLite, nunca llama al banco en caliente**. La sincronización
es un proceso aparte (`finmcp sync`, manual o por cron).

## Crea tu app de TrueLayer (2 minutos, gratis)

Cada usuario usa **sus propias credenciales** de TrueLayer (así nadie depende de un
servidor central ni comparte secretos). Conseguirlas en sandbox es gratis y rápido:

1. Entra en **[console.truelayer.com](https://console.truelayer.com)** y crea una cuenta.
2. Crea una aplicación (botón *Create application* / *New app*). Empiezas en **Sandbox**.
3. En la app, abre **Settings / Keys** y copia:
   - **Client ID** → a `TRUELAYER_CLIENT_ID` en tu `.env`.
   - **Client secret** → a `TRUELAYER_CLIENT_SECRET` en tu `.env`.
4. En **Redirect URIs**, añade exactamente:
   ```
   http://localhost:3000/callback
   ```
   (debe coincidir con `TRUELAYER_REDIRECT_URI` / `FINMCP_CALLBACK_PORT` del `.env`).
5. Deja `TRUELAYER_ENV=sandbox` y `TRUELAYER_PROVIDERS=uk-cs-mock` para probar contra el
   **Mock Bank** (datos ficticios, sin tocar dinero real).

> 🔒 **No compartas tu `Client secret` ni lo subas al repo** (ya está en `.gitignore` vía
> `.env`). Identifica a *tu* aplicación ante TrueLayer y todo el uso recae sobre tu cuenta.

> **¿Datos de tu banco real?** Necesitas que TrueLayer apruebe tu app para **`live`**
> (`TRUELAYER_ENV=live`) y elegir el provider de tu banco (ver [Bancos soportados](#bancos-soportados)).
> No es inmediato; para probar el proyecto, sandbox basta.

## Puesta en marcha

```bash
# 1. Clona y entra
git clone <tu-fork-o-este-repo> openbanking-mcp && cd openbanking-mcp

# 2. Entorno
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. Configura credenciales (sandbox)
cp .env.example .env
#   -> rellena TRUELAYER_CLIENT_ID y TRUELAYER_CLIENT_SECRET desde console.truelayer.com
#   -> registra la redirect URI http://localhost:3000/callback en tu app
#   -> elige tu banco en TRUELAYER_PROVIDERS (ver .env.example)

# 4. Autoriza (abre el navegador, Mock Bank en sandbox)
finmcp auth

# 5. Sincroniza datos a SQLite
finmcp sync

# 6. Revisa
finmcp accounts
```

## Bancos soportados

TrueLayer es un agregador PSD2 que cubre **cientos de bancos de UK y Europa**. Eliges cuál(es)
ofrecer en el diálogo de consentimiento mediante `TRUELAYER_PROVIDERS`:

| Caso | Valor de ejemplo |
|---|---|
| Sandbox (datos mock) | `uk-cs-mock` |
| Todos los bancos de un país (live) | `es-ob-all` · `uk-ob-all` · `fr-ob-all` … |
| Un banco concreto (live) | `es-ob-bbva` · `es-ob-santander` · `es-ob-caixabank` … |

> Los IDs exactos están en **console.truelayer.com → Data API → Providers**. El modo `live`
> requiere acceso aprobado por TrueLayer (no es inmediato); en `sandbox` solo existe el Mock Bank.

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

En `claude_desktop_config.json` (usa la **ruta absoluta** a tu clon del repo):

```json
{
  "mcpServers": {
    "openbanking": {
      "command": "/RUTA/ABSOLUTA/A/openbanking-mcp/.venv/bin/finmcp",
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
# Sustituye __PROJECT_DIR__ por la ruta absoluta de tu clon
sed -i '' "s|__PROJECT_DIR__|$PWD|g" deploy/com.openbanking-mcp.sync.plist

# Copia el LaunchAgent y actívalo (sync cada 6 h)
cp deploy/com.openbanking-mcp.sync.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.openbanking-mcp.sync.plist

# Logs en data/sync.log · para parar:
launchctl unload ~/Library/LaunchAgents/com.openbanking-mcp.sync.plist
```

## Notas PSD2

- El `access_token` dura ~1 h; se refresca solo con el `refresh_token`.
- PSD2 obliga a **re-consentir con SCA cada 90 días**: pasado ese plazo hay que repetir `finmcp auth`.
- El acceso `live` a bancos reales requiere una app de TrueLayer aprobada para producción.
  En `sandbox` se usa el Mock Bank de TrueLayer.

## Desarrollo

```bash
pip install -e ".[dev]"
pytest                       # suite de tests (analítica, mapper, sync)
```

La analítica son **funciones puras** testeadas contra una SQLite en memoria; el flujo de
`sync` se prueba con un cliente falso (sin tocar el banco). CI en GitHub Actions corre la
suite en Python 3.11–3.13 (`.github/workflows/ci.yml`).

## Licencia

[MIT](LICENSE) © 2026 Guille Pérez
