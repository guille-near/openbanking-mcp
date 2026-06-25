from __future__ import annotations

from finmcp.config import settings
from finmcp.providers.base import BankDataProvider


def get_provider() -> BankDataProvider:
    """Devuelve el proveedor Open Banking activo según `FINMCP_PROVIDER`."""
    prov = settings.provider.lower()
    if prov == "enablebanking":
        from finmcp.providers.enablebanking.client import EnableBankingClient

        return EnableBankingClient()
    if prov == "gocardless":
        from finmcp.providers.gocardless.client import GoCardlessClient

        return GoCardlessClient()
    from finmcp.providers.truelayer.client import TrueLayerClient

    return TrueLayerClient()
