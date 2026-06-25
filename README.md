# openbanking-mcp

Servidor MCP de **finanzas personales de solo lectura** sobre **Open Banking** (PSD2),
vía **[Enable Banking](https://enablebanking.com)**. Consulta cuentas, saldos y
movimientos de tu banco y genera analítica: gasto por categoría, suscripciones,
cargos inusuales y resúmenes mensuales — desde Claude Desktop, Cursor o ChatGPT.

> **Solo lectura.** No inicia pagos ni transferencias: solo se piden permisos de datos
> (cuentas, saldos y movimientos).

> **Funciona con casi toda la banca europea** (CaixaBank incluido). El banco se elige
> con `ENABLEBANKING_ASPSP_NAME` en tu `.env`.

## Aviso

Proyecto independiente, **no afiliado ni respaldado por Enable Banking ni por ningún banco**.
Manejas **tus propios datos bancarios** bajo tu responsabilidad: cada quien autohospeda
con sus credenciales y los datos **nunca salen de tu máquina** (SQLite local; tokens y
clave privada cifrados/protegidos en `data/`, que está en `.gitignore`). Software
entregado "tal cual", sin garantías (ver [LICENSE](LICENSE)). Lee las [notas PSD2](#notas-psd2).

## Arquitectura

```txt
Tu banco (PSD2)
   -> Enable Banking (AIS)          [interfaz BankDataProvider]
   -> Capa de sincronización        (pull idempotente e incremental)
   -> SQLite (SQLAlchemy)
   -> Capa de analítica             (funciones puras)
   -> Servidor MCP (solo lectura)
   -> Cliente MCP: Claude Desktop / Cursor / ChatGPT
```

El servidor MCP **lee de SQLite, nunca llama al banco en caliente**. La sincronización
es un proceso aparte (`finmcp sync`, manual o por cron).

> ¿Por qué Enable Banking? Es el agregador AIS **self-serve y gratis para uso personal**
> que cubre la banca europea. (GoCardless/Nordigen cerró nuevos registros y la Data API de
> TrueLayer ya no se concede self-serve.) El código mantiene una interfaz `BankDataProvider`,
> así que añadir otro proveedor es sencillo.

## Paso a paso

### 1. Instala el proyecto

```bash
git clone https://github.com/guille-near/openbanking-mcp.git && cd openbanking-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Registra tu app en Enable Banking

1. Entra en **[enablebanking.com](https://enablebanking.com) → Control Panel** y regístrate.
2. Crea una **aplicación**:
   - Generación de clave: **"Generate in the browser… export private key"**.
   - **Allowed redirect URLs**: `https://localhost:3000/callback` (exige **HTTPS**).
   - Rellena nombre, email y (si los pide) URLs de privacidad/términos.
3. Al registrar, **descarga la clave privada** (`.pem`) — **solo se muestra una vez** — y
   **copia el Application ID** (es el nombre del fichero `.pem`).
4. **Restricted Production**: en la app, pulsa **Link accounts** y vincula (lista blanca)
   las cuentas de tu banco que quieras leer. En modo *Restricted* solo se pueden acceder
   esas cuentas (no requiere due diligence; perfecto para uso personal).

### 3. Configura el `.env`

```bash
cp .env.example .env
```

Guarda la clave privada en `data/enablebanking_private.pem` y edita el `.env`:

```dotenv
FINMCP_PROVIDER=enablebanking
ENABLEBANKING_APP_ID=<tu Application ID>
ENABLEBANKING_COUNTRY=ES
# ENABLEBANKING_KEY_PATH=/ruta/a/clave.pem   # solo si NO usas data/enablebanking_private.pem
```

### 4. Elige tu banco

```bash
finmcp institutions            # lista las entidades (p.ej. "CaixaBank · ES")
```
Fija el nombre **exacto** en el `.env`:
```dotenv
ENABLEBANKING_ASPSP_NAME=CaixaBank
```

### 5. Autoriza y sincroniza

```bash
finmcp auth        # abre tu banco para el SCA
finmcp sync        # baja cuentas/saldos/movimientos a SQLite
finmcp accounts    # comprobación
```

En `finmcp auth`, tras el SCA el navegador irá a `https://localhost:3000/callback` y
mostrará un **error de conexión: es normal**. Copia el valor de `code` de la barra de
direcciones (o pega la URL entera) cuando el CLI lo pida. El código nunca sale de tu máquina.

> El consentimiento dura **~90 días** (límite PSD2); pasado ese plazo, repite `finmcp auth`.

## Comandos

| Comando | Descripción |
|---|---|
| `finmcp auth` | Autoriza con tu banco y guarda la sesión cifrada |
| `finmcp institutions` | Lista las entidades disponibles (para fijar `ENABLEBANKING_ASPSP_NAME`) |
| `finmcp sync` | Trae cuentas/saldos/movimientos a SQLite |
| `finmcp accounts` | Lista las cuentas locales |
| `finmcp import-csv` | Importa movimientos desde un CSV (histórico anterior a 90 días) |
| `finmcp categorize` | Reaplica tus reglas de categorización |
| `finmcp rules add/list` | Gestiona reglas de categorización |
| `finmcp serve` | Arranca el servidor MCP (stdio; `--http` para remoto) |

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

ChatGPT solo se conecta a servidores MCP **remotos por HTTP(S)**. Hay que exponer el
servidor por una URL pública y añadirlo como *connector* en Modo Desarrollador.

> ⚠️ **Datos bancarios por una URL pública.** Usa SIEMPRE bearer token y HTTPS.
> Para uso solo-local, Claude Desktop (stdio) es más seguro.

```bash
export FINMCP_HTTP_TOKEN="<token-largo-aleatorio>"
finmcp serve --http --port 8000        # expone POST /mcp (401 sin el token)
ngrok http 8000                         # túnel HTTPS -> https://xxxx.ngrok.app
```

En ChatGPT → Connectors → *Add custom connector*: URL `https://xxxx.ngrok.app/mcp`,
cabecera `Authorization: Bearer <FINMCP_HTTP_TOKEN>`.

## Categorías personalizadas

Enable Banking no envía categoría en los movimientos, así que las defines tú con reglas:

```bash
finmcp rules add "mercadona" "Supermercado"
finmcp rules add "vodafone" "Telefonía" --field merchant
finmcp rules list
finmcp categorize            # reaplica todas las reglas
```

Las reglas se reaplican automáticamente al final de cada `finmcp sync`.
`my_category` (manual/regla) tiene prioridad sobre cualquier categoría del proveedor.

## Importar histórico antiguo (CSV)

Las APIs PSD2 solo dan ~90 días de histórico. Para movimientos más antiguos,
exporta tus movimientos desde la web de tu banco (**Excel `.xlsx` o CSV/TXT**) e impórtalos:

```bash
finmcp import-csv movimientos.xlsx --iban ES58...   # o un .csv / .txt
```

Acepta **Excel (`.xlsx` y `.xls`) y texto (CSV/TXT)**; detecta el delimitador, las
cabeceras y el formato español de fecha/importe. Soporta importe en una columna con
signo o en columnas **Ingreso/Gasto** separadas (formato CaixaBank), y si el fichero
trae varias cuentas (columna *Número de cuenta*) **mapea cada movimiento a su cuenta**.
**Deduplica** por (cuenta, día, importe, tipo), así que es seguro reimportar o
solapar con lo que ya bajó la API. Las reglas de categorización se aplican solas.

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

- El consentimiento PSD2 caduca: hay que **re-autorizar con SCA cada ~90 días** (`finmcp auth`).
- En **Restricted Production** solo se leen las cuentas que hayas vinculado (lista blanca)
  en el panel de Enable Banking.
- El histórico disponible suele limitarse a ~90 días por las APIs PSD2 de los bancos.

## Desarrollo

```bash
pip install -e ".[dev]"
pytest                       # suite de tests (analítica, mapper, sync, config)
```

La analítica son **funciones puras** testeadas contra una SQLite en memoria; el flujo de
`sync` se prueba con un cliente falso (sin tocar el banco). CI en GitHub Actions corre la
suite en Python 3.11–3.13 (`.github/workflows/ci.yml`).

## Licencia

[MIT](LICENSE) © 2026 Guille Pérez
