from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Modelos normalizados, independientes del proveedor (TrueLayer, GoCardless, ...).
# La capa de mapeo de cada proveedor traduce su JSON a estos tipos.


@dataclass
class Account:
    provider_account_id: str
    name: str
    type: str
    currency: str
    iban: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class Balance:
    available: float | None
    current: float | None
    currency: str
    snapshot_at: datetime
    raw: dict = field(default_factory=dict)


@dataclass
class Transaction:
    provider_id: str
    amount: float  # siempre positivo; el signo va en `type`
    currency: str
    booked_at: datetime
    description: str
    type: str  # "debit" | "credit"
    merchant_name: str | None = None
    provider_category: str | None = None
    raw: dict = field(default_factory=dict)
