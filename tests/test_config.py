from __future__ import annotations

from finmcp.config import Settings


def test_provider_reads_finmcp_provider_env(monkeypatch):
    # El campo se llama `provider` pero debe leerse de FINMCP_PROVIDER (alias).
    monkeypatch.setenv("FINMCP_PROVIDER", "enablebanking")
    s = Settings(_env_file=None)
    assert s.provider == "enablebanking"


def test_provider_defaults_to_truelayer(monkeypatch):
    monkeypatch.delenv("FINMCP_PROVIDER", raising=False)
    monkeypatch.delenv("PROVIDER", raising=False)
    s = Settings(_env_file=None)
    assert s.provider == "truelayer"
