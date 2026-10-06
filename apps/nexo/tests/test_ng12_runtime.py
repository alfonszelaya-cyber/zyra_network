import json, pathlib, pytest, threading, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.services.runtime import NexoRuntime
from apps.nexo.services.menu_server_patch import apply_menu_routes

def test_runtime_emit_status_classify(tmp_path):
    rt = NexoRuntime(db=SQLiteAdapter(tmp_path / "rt.db"),
        clock=FrozenClock())
    r = rt.emit("NEXO_PAYMENT_RECEIVED",
        company_id="EMP-1",
        payload={"amount": "10"})
    assert r["buffered"] is True
    assert rt.bus.pending() == 1
    with pytest.raises(ValueError):
        rt.emit("EVENTO_FALSO")
    c = rt.classify_document(
        "factura de venta de servicios")
    assert c["category"] == "venta"
    st = rt.status()
    assert st["currency_mode"] == "static_fallback"
    assert st["events_pending"] == 1
    assert len(rt.drain_events()) == 1
    a = rt.audit_event(event="PRUEBA", actor="sys",
        entity="EMP-1")
    assert a["recorded"] is True
    print("OK runtime: eventos+IA+audit+status")

def test_menus_http_endpoint():
    class Dummy(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(404)
            self.end_headers()
        def log_message(self, *a):
            pass
    apply_menu_routes(Dummy)
    srv = HTTPServer(("127.0.0.1", 0), Dummy)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever,
                          daemon=True)
    th.start()
    try:
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/nexo/menus" % port,
                timeout=5) as resp:
            data = json.loads(resp.read().decode())
        assert data["total"] == 149
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/nexo/menus/"
                "accounting.asientos" % port,
                timeout=5) as resp:
            one = json.loads(resp.read().decode())
        assert one["menu_id"] == "accounting.asientos"
        fell = False
        try:
            urllib.request.urlopen(
                "http://127.0.0.1:%d/nexo/otra-cosa"
                % port, timeout=5)
            fell = True
        except urllib.error.HTTPError as e:
            fell = (e.code == 404)
        assert fell is True
    finally:
        srv.shutdown()
    print("OK HTTP menus: lista 149 + uno + fallthrough")

def test_server_inyectado():
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "server.py").read_text(encoding="utf-8")
    assert "/nexo/menus" in src
    print("OK server.py: bloque /nexo/menus presente")
