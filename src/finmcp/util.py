from __future__ import annotations

import calendar
from datetime import datetime, timezone


def parse_date(value: str | None) -> datetime | None:
    """Acepta 'YYYY-MM-DD' o ISO 8601. Devuelve None si value es falsy."""
    if not value:
        return None
    if len(value) == 10:  # YYYY-MM-DD
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """Primer y último instante (UTC) de un mes."""
    last_day = calendar.monthrange(year, month)[1]
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    return start, end
