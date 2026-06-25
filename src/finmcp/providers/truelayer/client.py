from __future__ import annotations

import httpx

from finmcp.config import settings
from finmcp.providers.truelayer import mapper
from finmcp.providers.truelayer.auth import get_valid_access_token
from finmcp.providers.types import Account, Balance, Transaction


class TrueLayerClient:
    """Cliente de SOLO LECTURA de la TrueLayer Data API.

    Implementa la interfaz `BankDataProvider`.
    """

    def __init__(self) -> None:
        self._base = settings.api_base

    def _client(self) -> httpx.Client:
        token = get_valid_access_token()
        return httpx.Client(
            base_url=self._base,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

    def get_accounts(self) -> list[Account]:
        with self._client() as c:
            r = c.get("/data/v1/accounts")
            r.raise_for_status()
            return [mapper.to_account(x) for x in r.json().get("results", [])]

    def get_balance(self, account_id: str) -> Balance:
        with self._client() as c:
            r = c.get(f"/data/v1/accounts/{account_id}/balance")
            r.raise_for_status()
            return mapper.to_balance(r.json()["results"][0])

    def get_transactions(
        self,
        account_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[Transaction]:
        params: dict[str, str] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        with self._client() as c:
            r = c.get(
                f"/data/v1/accounts/{account_id}/transactions", params=params
            )
            r.raise_for_status()
            return [mapper.to_transaction(x) for x in r.json().get("results", [])]
