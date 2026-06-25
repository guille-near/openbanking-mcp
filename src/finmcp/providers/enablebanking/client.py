from __future__ import annotations

import httpx

from finmcp.config import settings
from finmcp.providers.enablebanking import auth, mapper
from finmcp.providers.types import Account, Balance, Transaction


class EnableBankingClient:
    """Cliente de SOLO LECTURA de Enable Banking (Account Information / PSD2).

    Implementa la interfaz `BankDataProvider`. Lee las cuentas vinculadas en el
    último `finmcp auth` (session) y consulta saldos y movimientos.
    """

    def __init__(self) -> None:
        self._base = settings.enablebanking_base
        self._link = auth.load_link()

    def _get(self, path: str, params: dict | None = None) -> dict:
        with httpx.Client(
            base_url=self._base, headers=auth.auth_headers(), timeout=30
        ) as c:
            r = c.get(path, params=params or {})
            r.raise_for_status()
            return r.json()

    def get_accounts(self) -> list[Account]:
        return [mapper.to_account(a) for a in self._link["accounts"]]

    def get_balance(self, account_id: str) -> Balance:
        data = self._get(f"/accounts/{account_id}/balances")
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

        raw: list[dict] = []
        cont: str | None = None
        while True:
            page_params = dict(params)
            if cont:
                page_params["continuation_key"] = cont
            data = self._get(f"/accounts/{account_id}/transactions", page_params)
            raw.extend(data.get("transactions", []))
            cont = data.get("continuation_key")
            if not cont:
                break
        return [mapper.to_transaction(x) for x in raw]
