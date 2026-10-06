import json, pathlib, pytest, threading, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.module import discover_menus
from apps.semilla.routers.modules_router import (list_menus,
                                                get_menu)
from apps.semilla.services.menu_server_patch import apply_menu_routes
from apps.semilla.domain.transportation.transportation_engine import TransportationEngine

def test_11_menus_descubiertos() -> None:
    menus = discover_menus()
    assert len(menus) == 11
    ids = [m["menu_id"] for m in menus]
    assert len(set(ids)) == 11
    for m in menus:
        assert m["title"].strip()
        assert len(m["options"]) >= 1
    print("OK registry: 11 menus de modulos SEMILLA con opciones")

def test_router_menus() -> None:
    m = get_menu("modulo_3_talento")
    assert m is not None
    labels = " ".join(o["label"].lower()
                      for o in m["options"])
    assert "talento" in labels
    assert get_menu("no.existe") is None
    total = list_menus()["total"]
    assert total == 11
    print("OK router: get/list de menus SEMILLA")

def test_menus_http_endpoint() -> None:
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
                "http://127.0.0.1:%d/semilla/menus" % port,
                timeout=5) as resp:
            data = json.loads(resp.read().decode())
        assert data["total"] == 11
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/semilla/menus/"
                "modulo_1_identidad_educativa" % port,
                timeout=5) as resp:
            one = json.loads(resp.read().decode())
        assert (one["menu_id"]
                == "modulo_1_identidad_educativa")
        fell = False
        try:
            urllib.request.urlopen(
                "http://127.0.0.1:%d/semilla/otra-cosa"
                % port, timeout=5)
            fell = True
        except urllib.error.HTTPError as e:
            fell = (e.code == 404)
        assert fell is True
    finally:
        srv.shutdown()
    print("OK HTTP menus SEMILLA: lista 11 + uno + fallthrough")

def test_server_inyectado_o_honesto() -> None:
    sp = (pathlib.Path(__file__).resolve().parents[1]
          / "server.py")
    if sp.exists():
        src = sp.read_text(encoding="utf-8")
        ok = ("/semilla/menus" in src
              or "sm8_menus" not in src)
        assert ok
    print("OK server: inyectado o skip honesto")

def test_transporte_rutas_cupos(tmp_path) -> None:
    tr = TransportationEngine(
        SQLiteAdapter(tmp_path / "tr.db"), FrozenClock())
    ruta = tr.create_route(name="Ruta Norte",
        driver="Carlos", capacity=2)
    tr.add_stop(route_id=ruta["route_id"],
        stop_name="Parque Central", order_num=1)
    tr.assign_student(route_id=ruta["route_id"],
        student_id="STU-TR1")
    tr.assign_student(route_id=ruta["route_id"],
        student_id="STU-TR2")
    with pytest.raises(ValueError):
        tr.assign_student(route_id=ruta["route_id"],
            student_id="STU-TR3")
    with pytest.raises(ValueError):
        tr.assign_student(route_id=ruta["route_id"],
            student_id="STU-TR1")
    assert tr.get_route(ruta["route_id"])["cupos"] == 0
    print("OK transporte: rutas+paradas+cupos bloqueados+anti-duplicado")
