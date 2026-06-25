from __future__ import annotations

import secrets
import time
import urllib.parse
import webbrowser
from datetime import datetime, timedelta, timezone

import httpx
import jwt

from finmcp.config import settings
from finmcp.security.tokens import load_secret, save_secret

# Vínculo (session + cuentas) cifrado en data/enablebanking_link.enc
_LINK_STORE = "enablebanking_link"


# --- Autenticación: JWT RS256 firmado con la clave privada de la app ---------

def _build_jwt() -> str:
    if not settings.enablebanking_app_id:
        raise RuntimeError("Falta ENABLEBANKING_APP_ID en .env")
    key_path = settings.enablebanking_private_key
    if not key_path.exists():
        raise RuntimeError(
            f"No se encuentra la clave privada en {key_path}. "
            "Descárgala al registrar la app y fija ENABLEBANKING_KEY_PATH."
        )
    now = int(time.time())
    return jwt.encode(
        {
            "iss": "enablebanking.com",
            "aud": "api.enablebanking.com",
            "iat": now,
            "exp": now + 3600,  # máx. 24 h; 1 h sobra por petición
        },
        key_path.read_text(),
        algorithm="RS256",
        headers={"typ": "JWT", "kid": settings.enablebanking_app_id},
    )


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {_build_jwt()}"}


# --- Catálogo de entidades (ASPSPs) ------------------------------------------

def list_aspsps(country: str, psu_type: str = "personal") -> list[dict]:
    r = httpx.get(
        f"{settings.enablebanking_base}/aspsps",
        params={"country": country, "psu_type": psu_type},
        headers=auth_headers(),
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    return body.get("aspsps", []) if isinstance(body, dict) else body


# --- Flujo de consentimiento (auth + SCA + session) --------------------------
# Enable Banking exige redirect HTTPS, así que no levantamos un servidor local:
# el usuario pega el `code` que aparece en la URL tras el SCA. Más privado, además,
# porque el código nunca sale de la máquina.

def _extract_code(raw: str) -> str:
    """Acepta el `code` pelado o la URL completa de redirección y devuelve el code."""
    if "code=" in raw:
        query = urllib.parse.urlparse(raw).query or raw.split("?", 1)[-1]
        params = urllib.parse.parse_qs(query)
        if params.get("code"):
            return params["code"][0]
    return raw


def start_auth(aspsp_name: str, country: str, state: str) -> dict:
    # Redsys (banca española) admite como máximo 90 días de validez de consentimiento.
    valid_until = (datetime.now(timezone.utc) + timedelta(days=89)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    r = httpx.post(
        f"{settings.enablebanking_base}/auth",
        json={
            "aspsp": {"name": aspsp_name, "country": country},
            "access": {"valid_until": valid_until},
            "state": state,
            "redirect_url": settings.enablebanking_redirect_uri,
            "psu_type": "personal",
        },
        headers=auth_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def create_session(code: str) -> dict:
    r = httpx.post(
        f"{settings.enablebanking_base}/sessions",
        json={"code": code},
        headers=auth_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def run_link_flow() -> dict:
    name = settings.enablebanking_aspsp_name
    if not name:
        raise RuntimeError(
            "Falta ENABLEBANKING_ASPSP_NAME en .env. "
            "Lista las entidades con `finmcp institutions`."
        )
    state = secrets.token_urlsafe(16)
    auth_resp = start_auth(name, settings.enablebanking_country, state)
    print("Abre esta URL y autoriza con tu banco (SCA):\n")
    print(f"  {auth_resp['url']}\n")
    webbrowser.open(auth_resp["url"])
    print(
        "Tras autorizar, el navegador irá a "
        f"{settings.enablebanking_redirect_uri} y mostrará un error de conexión: es normal.\n"
        "Copia de la barra de direcciones el valor de 'code' (o pega la URL entera) y pégalo aquí.\n"
    )
    code = _extract_code(input("code: ").strip())

    session = create_session(code)
    save_secret(
        _LINK_STORE,
        {
            "session_id": session["session_id"],
            "accounts": session.get("accounts", []),
        },
    )
    print(f"Vínculo guardado · cuentas: {len(session.get('accounts', []))}")
    return session


def load_link() -> dict:
    link = load_secret(_LINK_STORE)
    if not link or not link.get("accounts"):
        raise RuntimeError(
            "No hay vínculo con el banco. Ejecuta `finmcp auth` primero."
        )
    return link
