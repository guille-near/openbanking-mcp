from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from cryptography.fernet import Fernet

from finmcp.config import settings


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: float  # epoch seconds (UTC)
    scope: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _key_path() -> Path:
    return settings.data_dir / "fernet.key"


def _load_or_create_key() -> bytes:
    """Clave Fernet: de la env si está, si no se genera y persiste con chmod 600."""
    if settings.finmcp_encryption_key:
        return settings.finmcp_encryption_key.encode()
    kp = _key_path()
    if kp.exists():
        return kp.read_bytes()
    key = Fernet.generate_key()
    kp.write_bytes(key)
    os.chmod(kp, 0o600)
    return key


def _fernet() -> Fernet:
    return Fernet(_load_or_create_key())


def _store_path() -> Path:
    return settings.data_dir / "tokens.enc"


def save_tokens(tokens: TokenSet) -> None:
    blob = _fernet().encrypt(json.dumps(tokens.as_dict()).encode())
    p = _store_path()
    p.write_bytes(blob)
    os.chmod(p, 0o600)


def load_tokens() -> TokenSet | None:
    p = _store_path()
    if not p.exists():
        return None
    data = json.loads(_fernet().decrypt(p.read_bytes()))
    return TokenSet(**data)
