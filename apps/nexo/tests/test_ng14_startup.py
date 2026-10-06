import importlib, pathlib, pytest
from shared_engines.common.clocks import SystemClock
from apps.nexo.services.startup import attach_live_runtime

class FakeStore:
    def __init__(self):
        self._db = None

class FakeClient:
    pass

class FakeServer:
    def __init__(self):
        self.RequestHandlerClass = None

def test_attach_con_client_conecta(tmp_path):
    server = FakeServer()
    rt = attach_live_runtime({"server": server,
        "store": FakeStore(),
        "client": FakeClient()})
    assert rt is not None
    assert server.nexo_runtime is rt
    assert rt.link is not None
    assert rt.verification.mode == "nexo_link"
    assert "events_pending" in rt.status()
    print("OK attach: runtime vivo colgado en server")

def test_attach_sin_red_honesto():
    server = FakeServer()
    rt = attach_live_runtime({"server": server,
        "store": FakeStore()})
    assert rt.verification.mode == "not_configured"
    assert rt.link is None
    r = rt.emit("NEXO_PERIOD_CLOSED",
        company_id="EMP-1", payload={})
    assert r["buffered"] is True
    print("OK attach sin Red: runtime honesto en buffer")

def test_attach_idempotente():
    server = FakeServer()
    r1 = attach_live_runtime({"server": server,
        "store": FakeStore()})
    r2 = attach_live_runtime({"server": server,
        "store": FakeStore()})
    assert r1 is r2
    print("OK attach: idempotente (misma instancia)")

def test_attach_defensivo_none():
    rt = attach_live_runtime(None)
    assert rt is not None
    assert rt.status()["ai_mode"] in ("ai_chain",
                                      "rules_fallback")
    print("OK attach None: no lanza, runtime honesto")

def test_superapp_inyectado_e_importa():
    src = (pathlib.Path.cwd()
           / "superapp.py").read_text(encoding="utf-8")
    assert "_ng_start_nexo_base" in src
    assert "attach_live_runtime" in src
    sup = importlib.import_module("superapp")
    assert hasattr(sup, "_start_nexo")
    print("OK superapp: wrapper presente y modulo importa")
