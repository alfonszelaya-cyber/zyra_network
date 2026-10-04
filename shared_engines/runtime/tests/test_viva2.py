"""VIVA-2: conectores vivos + sweep + FX 5 fuentes."""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from decimal import Decimal

from shared_engines.common.clocks import FrozenClock
from shared_engines.currency.contracts import CurrencyPair
from shared_engines.currency.rates import (
    FrankfurterRateProvider, KrakenRateProvider)
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.runtime.capabilities import ZyraCapabilities
from shared_engines.runtime.combined_api import serve_combined
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import Ed25519Signer


class _R:
    def __init__(self, p):
        self._p = p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._p


_REAL_URLOPEN = urllib.request.urlopen


def _stack(tmp_path):
    db = SQLiteAdapter(tmp_path / "v2.db")
    s, _ = Ed25519Signer.generate()
    k = ZyraKernel(
        db=db, clock=FrozenClock(), signer=s,
        config=RuntimeConfig(
            host="127.0.0.1", port=0,
            api_token=None))
    k.bootstrap_root()
    caps = ZyraCapabilities(
        db, FrozenClock(),
        identity=k.identity, signer=s)
    return k, caps, db


def test_integrations_wired(tmp_path) -> None:
    k, caps, db = _stack(tmp_path)
    h = caps.integrations.health(
        adapter_id="onec-classifiers")
    assert "onec" in h.endpoint, str(h)
    h2 = caps.integrations.health(
        adapter_id="marn-geo")
    assert "marn" in h2.endpoint, str(h2)
    assert caps._source_client is not None
    print("OK VIVA-2: integrations cableado ONEC+MARN")


def test_frankfurter_parse(tmp_path, monkeypatch) -> None:
    payload = json.dumps({
        "amount": 1.0, "base": "USD",
        "rates": {"EUR": 0.89087}}).encode()

    def fake(req, timeout=None):
        return _R(payload)

    monkeypatch.setattr(
        "urllib.request.urlopen", fake)
    q = FrankfurterRateProvider().fetch(
        CurrencyPair("USD", "EUR"), FrozenClock())
    assert q.rate == Decimal("0.89087"), str(q)
    assert q.source == "frankfurter"
    print("OK VIVA-2: frankfurter 0.89087")


def test_kraken_parse(tmp_path, monkeypatch) -> None:
    payload = json.dumps({
        "result": {"XXBTZUSD": {
            "c": ["84749.20000", "1.0"]}}}).encode()

    def fake(req, timeout=None):
        return _R(payload)

    monkeypatch.setattr(
        "urllib.request.urlopen", fake)
    q = KrakenRateProvider().fetch(
        CurrencyPair("BTC", "USD"), FrozenClock())
    assert q.rate == Decimal("84749.20000"), str(q)
    assert q.source == "kraken"
    print("OK VIVA-2: kraken BTC 84749.20")


def test_sources_sweep_route(tmp_path, monkeypatch) -> None:
    """VIVA-2: la ruta /sources/sweep desvia
    las llamadas a onec al fake y deja pasar
    el propio POST del test (localhost) al
    urlopen real."""
    k, caps, db = _stack(tmp_path)
    one_body = json.dumps(
        [{"codigo": "0111101"}]).encode()

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if "127.0.0.1" in url or "localhost" in url:
            return _REAL_URLOPEN(req, timeout=timeout)
        if "onec.bcr.gob.sv" in url:
            return _R(one_body)
        raise OSError("no simulada: " + url[:80])

    monkeypatch.setattr(
        "urllib.request.urlopen", fake_urlopen)
    srv = serve_combined(
        k, caps, host="127.0.0.1", port=0)
    threading.Thread(
        target=srv.serve_forever,
        daemon=True).start()
    time.sleep(0.4)
    base = "http://127.0.0.1:" + str(
        srv.server_address[1])
    req = urllib.request.Request(
        base + "/sources/sweep",
        data=json.dumps({"source": "onec"}).encode(),
        method="POST",
        headers={"Content-Type":
                 "application/json"})
    with _REAL_URLOPEN(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    assert d["data"]["ok"] == 7, str(d)[:200]
    print("OK VIVA-2: /sources/sweep onec 7/7 via HTTP")
    srv.shutdown()
    srv.server_close()
