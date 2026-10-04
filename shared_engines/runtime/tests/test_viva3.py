"""VIVA-3: token obligatorio + rate limit."""
from __future__ import annotations

import threading
import time
import urllib.request
import urllib.error

from shared_engines.common.clocks import SystemClock
from shared_engines.runtime.config import RuntimeConfig
from shared_engines.runtime.kernel import ZyraKernel
from shared_engines.runtime.capabilities import (
    ZyraCapabilities)
from shared_engines.runtime.combined_api import (
    serve_combined, RateLimiter)
import shared_engines.runtime.combined_api as _capi
from shared_engines.storage.database import SQLiteAdapter
from shared_engines.verification.signatures import (
    Ed25519Signer)


def _stack(tmp_path, api_token=None):
    db = SQLiteAdapter(tmp_path / "v3.db")
    s, _ = Ed25519Signer.generate()
    k = ZyraKernel(
        db=db, clock=SystemClock(), signer=s,
        config=RuntimeConfig(
            host="127.0.0.1", port=0,
            api_token=api_token))
    k.bootstrap_root()
    caps = ZyraCapabilities(
        db, SystemClock(),
        identity=k.identity, signer=s)
    srv = serve_combined(
        k, caps, host="127.0.0.1", port=0)
    threading.Thread(
        target=srv.serve_forever,
        daemon=True).start()
    time.sleep(0.4)
    base = ("http://127.0.0.1:"
            + str(srv.server_address[1]))
    return base, srv


def _get(base, ruta, header=None):
    h = {}
    if header:
        h["Authorization"] = header
    req = urllib.request.Request(
        base + ruta, headers=h)
    try:
        with urllib.request.urlopen(
                req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_rate_limiter_unit() -> None:
    rl = RateLimiter(max_per_minute=3)
    assert rl.allow("1.2.3.4") is True
    assert rl.allow("1.2.3.4") is True
    assert rl.allow("1.2.3.4") is True
    assert rl.allow("1.2.3.4") is False
    assert rl.allow("5.6.7.8") is True
    print("OK VIVA-3: rate limiter 3/min por IP")


def test_auth_enforced_con_token(tmp_path) -> None:
    base, srv = _stack(
        tmp_path,
        api_token="test-token-12345678")
    try:
        code = _get(base, "/tokens/items")
        assert code == 401, str(code)
        code2 = _get(
            base, "/tokens/items",
            header="Bearer test-token-12345678")
        assert code2 != 401, str(code2)
        code3 = _get(base, "/health")
        assert code3 == 200, str(code3)
        print("OK VIVA-3: token exigido; publicas libres")
    finally:
        srv.shutdown()
        srv.server_close()


def test_rate_limit_429(tmp_path) -> None:
    base, srv = _stack(tmp_path)
    viejo = _capi._RATE_LIMITER._max
    _capi._RATE_LIMITER._max = 3
    _capi._RATE_LIMITER._hits.clear()
    try:
        codigos = [
            _get(base, "/tokens/items")
            for _ in range(5)]
        assert 429 in codigos, str(codigos)
        assert codigos[0] != 429
        h = _get(base, "/health")
        assert h == 200, str(h)
        print("OK VIVA-3: 429 al exceder; health exenta")
    finally:
        _capi._RATE_LIMITER._max = viejo
        _capi._RATE_LIMITER._hits.clear()
        srv.shutdown()
        srv.server_close()


def test_sin_env_comportamiento_actual(tmp_path) -> None:
    base, srv = _stack(tmp_path)
    try:
        code = _get(base, "/tokens/items")
        assert code == 200, str(code)
        print("OK VIVA-3: sin env todo como siempre")
    finally:
        srv.shutdown()
        srv.server_close()
