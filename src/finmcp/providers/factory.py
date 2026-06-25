from __future__ import annotations

from finmcp.config import settings
from finmcp.providers.base import BankDataProvider


def get_provider() -> BankDataProvider:
    """Devuelve el proveedor Open Banking activo según `FINMCP_PROVIDER`."""
    if settings.provider.lower() == "gocardless":
        from finmcp.providers.gocardless.client import GoCardlessClient

        return GoCardlessClient()
    from finmcp.providers.truelayer.client import TrueLayerClient

    return TrueLayerClient()
