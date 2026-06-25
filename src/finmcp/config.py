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

    # --- Proveedor Open Banking activo ---
    provider: str = Field(
        "truelayer", description='"truelayer" | "gocardless" | "enablebanking"'
    )

    # --- TrueLayer ---
    truelayer_env: str = Field("sandbox", description='"sandbox" | "live"')
    truelayer_client_id: str = ""
    truelayer_client_secret: str = ""
    truelayer_redirect_uri: str = "http://localhost:3000/callback"
    truelayer_providers: str = "uk-cs-mock"

    # --- GoCardless Bank Account Data (antes Nordigen) ---
    gocardless_secret_id: str = ""
    gocardless_secret_key: str = ""
    gocardless_institution_id: str = ""  # p.ej. CAIXABANK_CAIXESBBXXX
    gocardless_country: str = "es"
    gocardless_redirect_uri: str = "http://localhost:3000/callback"

    # --- Enable Banking ---
    enablebanking_app_id: str = ""  # Application ID (kid del JWT)
    enablebanking_key_path: Path | None = None  # ruta al .pem de la clave privada
    enablebanking_aspsp_name: str = ""  # nombre exacto del banco, p.ej. CaixaBank
    enablebanking_country: str = "ES"
    enablebanking_redirect_uri: str = "http://localhost:3000/callback"

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

    @property
    def gocardless_base(self) -> str:
        return "https://bankaccountdata.gocardless.com/api/v2"

    @property
    def enablebanking_base(self) -> str:
        return "https://api.enablebanking.com"

    @property
    def enablebanking_private_key(self) -> Path:
        return self.enablebanking_key_path or (
            self.data_dir / "enablebanking_private.pem"
        )


settings = Settings()
