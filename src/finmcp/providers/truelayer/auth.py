from __future__ import annotations

import secrets
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

from finmcp.config import settings
from finmcp.security.tokens import TokenSet, load_tokens, save_tokens


def build_auth_url(state: str, nonce: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.truelayer_client_id,
        "scope": " ".join(settings.scopes),
        "redirect_uri": settings.truelayer_redirect_uri,
        "providers": settings.truelayer_providers,
        "state": state,
        "nonce": nonce,
    }
    return f"{settings.auth_base}/?{urllib.parse.urlencode(params)}"


class _CallbackHandler(BaseHTTPRequestHandler):
    code: str | None = None
    state: str | None = None

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        qs = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.code = qs.get("code", [None])[0]
        _CallbackHandler.state = qs.get("state", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = _CallbackHandler.code is not None
        body = (
            "<h2>Autorizacion recibida. Ya puedes cerrar esta pestana.</h2>"
            if ok
            else "<h2>No se recibio el codigo de autorizacion.</h2>"
        )
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args):  # silenciar logs del servidor
        pass


def _wait_for_code(port: int, expected_state: str) -> str:
    _CallbackHandler.code = None
    _CallbackHandler.state = None
    server = HTTPServer(("localhost", port), _CallbackHandler)
    # Atiende peticiones (incluida alguna a /favicon.ico) hasta recibir el code.
    while _CallbackHandler.code is None:
        server.handle_request()
    server.server_close()
    if _CallbackHandler.state != expected_state:
        raise RuntimeError("State mismatch: posible CSRF, abortando.")
    return _CallbackHandler.code


def _to_tokenset(payload: dict, fallback_refresh: str | None = None) -> TokenSet:
    return TokenSet(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token", fallback_refresh),
        expires_at=time.time() + int(payload.get("expires_in", 3600)),
        scope=payload.get("scope", ""),
    )


def exchange_code(code: str) -> TokenSet:
    resp = httpx.post(
        f"{settings.auth_base}/connect/token",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.truelayer_client_id,
            "client_secret": settings.truelayer_client_secret,
            "redirect_uri": settings.truelayer_redirect_uri,
            "code": code,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return _to_tokenset(resp.json())


def refresh_tokens(refresh_token: str) -> TokenSet:
    resp = httpx.post(
        f"{settings.auth_base}/connect/token",
        data={
            "grant_type": "refresh_token",
            "client_id": settings.truelayer_client_id,
            "client_secret": settings.truelayer_client_secret,
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return _to_tokenset(resp.json(), fallback_refresh=refresh_token)


def run_authorization_flow() -> TokenSet:
    if not settings.truelayer_client_id or not settings.truelayer_client_secret:
        raise RuntimeError(
            "Faltan TRUELAYER_CLIENT_ID / TRUELAYER_CLIENT_SECRET en .env"
        )
    state = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16)
    url = build_auth_url(state, nonce)
    print("Abriendo el navegador para autorizar con TrueLayer...")
    print(f"Si no se abre, visita:\n{url}\n")
    webbrowser.open(url)
    code = _wait_for_code(settings.finmcp_callback_port, state)
    tokens = exchange_code(code)
    save_tokens(tokens)
    print("Tokens guardados y cifrados.")
    return tokens


def get_valid_access_token() -> str:
    """Devuelve un access_token válido, refrescándolo si está por expirar."""
    tokens = load_tokens()
    if tokens is None:
        raise RuntimeError("No hay tokens. Ejecuta `finmcp auth` primero.")
    if tokens.expires_at - time.time() < 60:
        if not tokens.refresh_token:
            raise RuntimeError("Token expirado y sin refresh_token. Re-autoriza.")
        tokens = refresh_tokens(tokens.refresh_token)
        save_tokens(tokens)
    return tokens.access_token
