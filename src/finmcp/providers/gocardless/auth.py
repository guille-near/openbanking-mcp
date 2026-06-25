from __future__ import annotations

import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

from finmcp.config import settings
from finmcp.security.tokens import load_secret, save_secret

# Ficheros cifrados (en data/) donde se guardan el token y el vínculo (requisition).
_TOKEN_STORE = "gocardless_token"
_LINK_STORE = "gocardless_link"


# --- Token (secret_id/secret_key -> access/refresh) --------------------------

def _token_url(path: str) -> str:
    return f"{settings.gocardless_base}/token/{path}/"


def _new_token() -> dict:
    if not settings.gocardless_secret_id or not settings.gocardless_secret_key:
        raise RuntimeError(
            "Faltan GOCARDLESS_SECRET_ID / GOCARDLESS_SECRET_KEY en .env"
        )
    r = httpx.post(
        _token_url("new"),
        json={
            "secret_id": settings.gocardless_secret_id,
            "secret_key": settings.gocardless_secret_key,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    now = time.time()
    record = {
        "access": data["access"],
        "access_expires_at": now + int(data.get("access_expires", 86400)),
        "refresh": data.get("refresh"),
        "refresh_expires_at": now + int(data.get("refresh_expires", 2592000)),
    }
    save_secret(_TOKEN_STORE, record)
    return record


def _refresh_token(refresh: str) -> dict | None:
    r = httpx.post(_token_url("refresh"), json={"refresh": refresh}, timeout=30)
    if r.status_code != 200:
        return None
    data = r.json()
    rec = load_secret(_TOKEN_STORE) or {}
    rec["access"] = data["access"]
    rec["access_expires_at"] = time.time() + int(data.get("access_expires", 86400))
    save_secret(_TOKEN_STORE, rec)
    return rec


def get_access_token() -> str:
    """Access token válido: reutiliza, refresca o pide uno nuevo según convenga."""
    rec = load_secret(_TOKEN_STORE)
    now = time.time()
    if rec and rec.get("access_expires_at", 0) - now > 60:
        return rec["access"]
    if rec and rec.get("refresh") and rec.get("refresh_expires_at", 0) - now > 60:
        refreshed = _refresh_token(rec["refresh"])
        if refreshed:
            return refreshed["access"]
    return _new_token()["access"]


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {get_access_token()}"}


# --- Catálogo de entidades ---------------------------------------------------

def list_institutions(country: str) -> list[dict]:
    r = httpx.get(
        f"{settings.gocardless_base}/institutions/",
        params={"country": country},
        headers=auth_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# --- Flujo de consentimiento (requisition + SCA) -----------------------------

class _ReturnHandler(BaseHTTPRequestHandler):
    hit = False

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        _ReturnHandler.hit = True
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            "<h2>Consentimiento recibido. Ya puedes cerrar esta pestana.</h2>".encode(
                "utf-8"
            )
        )

    def log_message(self, *args):  # silenciar logs del servidor
        pass


def _wait_for_return(port: int) -> None:
    _ReturnHandler.hit = False
    server = HTTPServer(("localhost", port), _ReturnHandler)
    while not _ReturnHandler.hit:
        server.handle_request()
    server.server_close()


def create_requisition(institution_id: str) -> dict:
    r = httpx.post(
        f"{settings.gocardless_base}/requisitions/",
        json={
            "redirect": settings.gocardless_redirect_uri,
            "institution_id": institution_id,
            "user_language": "ES",
        },
        headers=auth_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_requisition(requisition_id: str) -> dict:
    r = httpx.get(
        f"{settings.gocardless_base}/requisitions/{requisition_id}/",
        headers=auth_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def run_link_flow() -> dict:
    """Crea la requisition, abre el banco para el SCA y guarda las cuentas vinculadas."""
    institution = settings.gocardless_institution_id
    if not institution:
        raise RuntimeError(
            "Falta GOCARDLESS_INSTITUTION_ID en .env. "
            "Lista las entidades con `finmcp institutions`."
        )
    req = create_requisition(institution)
    print("Abriendo el navegador para autorizar con tu banco (vía GoCardless)...")
    print(f"Si no se abre, visita:\n{req['link']}\n")
    webbrowser.open(req["link"])
    _wait_for_return(settings.finmcp_callback_port)

    # Tras el consentimiento, las cuentas pueden tardar un instante en propagarse.
    detail = get_requisition(req["id"])
    for _ in range(5):
        if detail.get("accounts"):
            break
        time.sleep(1)
        detail = get_requisition(req["id"])

    save_secret(
        _LINK_STORE,
        {"requisition_id": req["id"], "accounts": detail.get("accounts", [])},
    )
    print(f"Vínculo guardado · cuentas: {len(detail.get('accounts', []))}")
    return detail


def load_link() -> dict:
    link = load_secret(_LINK_STORE)
    if not link or not link.get("accounts"):
        raise RuntimeError(
            "No hay vínculo con el banco. Ejecuta `finmcp auth` primero."
        )
    return link
