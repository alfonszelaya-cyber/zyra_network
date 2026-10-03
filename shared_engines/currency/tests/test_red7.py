
"""RED-7: LINK moneda + oraculo + tasas en vivo cartera."""
from __future__ import annotations

from decimal import Decimal

import pytest

from shared_engines.common.clocks import FrozenClock
from shared_engines.currency.contracts import CurrencyPair
from shared_engines.currency.errors import (
    RateUnavailableError)
from shared_engines.currency.rates import (
    CryptoRateProvider,
    ChainlinkOracleProvider,
    ProviderChain,
)


class _R:
    def __init__(self, p):
        self._p = p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._p


class _DeadProvider:
    name = "dead"

    def fetch(self, pair, clock):
        raise RateUnavailableError("down")


def test_link_as_currency(tmp_path, monkeypatch) -> None:
    payload = b'{"chainlink": {"usd": 14.52}}'

    def fake(req, timeout=None):
        return _R(payload)

    monkeypatch.setattr(
        "urllib.request.urlopen", fake)
    q = CryptoRateProvider().fetch(
        CurrencyPair("LINK", "USD"),
        FrozenClock())
    assert q.rate == Decimal("14.52"), str(q)
    assert q.source == "coingecko"
    print("OK RED-7: LINK 14.52 USD via coingecko")


def test_chainlink_oracle_fallback(
    tmp_path, monkeypatch,
) -> None:
    payload = b'{"chainlink": {"usd": 14.60}}'

    def fake(req, timeout=None):
        return _R(payload)

    monkeypatch.setattr(
        "urllib.request.urlopen", fake)
    q = ChainlinkOracleProvider().fetch(
        CurrencyPair("LINK", "USD"),
        FrozenClock())
    assert q.rate == Decimal("14.60")
    assert q.source == "chainlink-oracle"
    chain = ProviderChain(
        [_DeadProvider(),
         ChainlinkOracleProvider()])
    q2 = chain.fetch(
        CurrencyPair("LINK", "USD"),
        FrozenClock())
    assert q2.source == "chainlink-oracle"
    print("OK RED-7: oraculo chainlink como fallback")


def test_cartera_get_live_rate_fiat(
    tmp_path, monkeypatch,
) -> None:
    import importlib.util as _iu
    import sqlite3 as _sq
    import sys as _sys
    spec = _iu.spec_from_file_location(
        "cartera_store_test",
        "apps/subastas/modules/motores"
        "/cartera_store.py")
    mod = _iu.module_from_spec(spec)
    _sys.modules["cartera_store_test"] = mod
    spec.loader.exec_module(mod)

    fake_json = (
        b'{"conversion_rates": {"GTQ": 7.75}}')

    def fake(req, timeout=None):
        return _R(fake_json)

    monkeypatch.setattr(
        "urllib.request.urlopen", fake)

    class _CK:
        def now(self):
            return 1000000.0

    store = mod.CarteraStore(
        _sq.connect(":memory:"), _CK())
    r = store.get_live_rate(
        from_cur="USD", to_cur="GTQ")
    assert r["rate"] == 7.75, str(r)
    assert "er-api" in (r.get("source") or "")
    print("OK RED-7: cartera consulta er-api"
          " en vivo (manual manda en convert)")
