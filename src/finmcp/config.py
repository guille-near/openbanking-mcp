from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Scopes de SOLO LECTURA. Ninguno permite iniciar pagos ni transferencias.
SCOPES = [
    "info",
    "accounts",
    "balance",
    "transactions",
    "direct_debits",
    "standing_orders",
    "offline_access",  # necesario para obtener refresh_token
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- TrueLayer ---
    truelayer_env: str = Field("sandbox", description='"sandbox" | "live"')
    truelayer_client_id: str = ""
    truelayer_client_secret: str = ""
    truelayer_redirect_uri: str = "http://localhost:3000/callback"
    truelayer_providers: str = "uk-cs-mock"

    # --- Almacenamiento ---
    finmcp_db_path: Path | None = None

    # --- Seguridad ---
    finmcp_encryption_key: str = ""
    finmcp_callback_port: int = 3000

    @property
    def is_sandbox(self) -> bool:
        return self.truelayer_env.lower() != "live"

    @property
    def auth_base(self) -> str:
        return (
            "https://auth.truelayer-sandbox.com"
            if self.is_sandbox
            else "https://auth.truelayer.com"
        )

    @property
    def api_base(self) -> str:
        return (
            "https://api.truelayer-sandbox.com"
            if self.is_sandbox
            else "https://api.truelayer.com"
        )

    @property
    def data_dir(self) -> Path:
        d = Path(__file__).resolve().parents[2] / "data"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def db_path(self) -> Path:
        return self.finmcp_db_path or (self.data_dir / "finmcp.db")

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def scopes(self) -> list[str]:
        return SCOPES


settings = Settings()
