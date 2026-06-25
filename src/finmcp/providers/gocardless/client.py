from __future__ import annotations

import httpx

from finmcp.config import settings
from finmcp.providers.gocardless import auth, mapper
from finmcp.providers.types import Account, Balance, Transaction


class GoCardlessClient:
    """Cliente de SOLO LECTURA de GoCardless Bank Account Data (AIS / Nordigen).

    Implementa la interfaz `BankDataProvider`. Lee las cuentas vinculadas en el
    último `finmcp auth` (requisition) y consulta saldos y movimientos.
    """

    def __init__(self) -> None:
        self._base = settings.gocardless_base
        self._link = auth.load_link()

    def _get(self, path: str, params: dict | None = None) -> dict:
        with httpx.Client(
            base_url=self._base, headers=auth.auth_headers(), timeout=30
        ) as c:
            r = c.get(path, params=params or {})
            r.raise_for_status()
            return r.json()

    def get_accounts(self) -> list[Account]:
        out: list[Account] = []
        for acc_id in self._link["accounts"]:
            meta = self._get(f"/accounts/{acc_id}/")
            details = self._get(f"/accounts/{acc_id}/details/").get("account", {})
            out.append(mapper.to_account(acc_id, meta, details))
        return out

    def get_balance(self, account_id: str) -> Balance:
        data = self._get(f"/accounts/{account_id}/balances/")
        return mapper.to_balance(data.get("balances", []))

    def get_transactions(
        self,
        account_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[Transaction]:
        params: dict[str, str] = {}
        if from_date:
            params["date_from"] = from_date
        if to_date:
            params["date_to"] = to_date
        data = self._get(f"/accounts/{account_id}/transactions/", params)
        booked = data.get("transactions", {}).get("booked", [])
        return [mapper.to_transaction(x) for x in booked]
