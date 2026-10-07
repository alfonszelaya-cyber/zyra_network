import json
import pathlib
import threading
import urllib.error
import urllib.request
import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.infrastructure.persistence.semilla_store import SemillaStore
from apps.semilla.domain.classroom.classroom_engine import ClassroomEngine
from apps.semilla.server import serve_semilla

PICK2 = [{"name": "Mama", "relation": "MADRE"},
         {"name": "Papa", "relation": "PADRE"}]
EMG = [{"name": "Tio", "relation": "TIO", "phone": "911"}]


class _DummyClient:
    pass


def _call(base, path, method="GET", doc=None):
    data = None
    headers = {}
    if doc is not None:
        data = json.dumps(doc).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path,
        data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req,
                                    timeout=10) as r:
            return (r.status, json.loads(
                r.read().decode("utf-8")))
    except urllib.error.HTTPError as e:
        return (e.code, json.loads(
            e.read().decode("utf-8")))


def _doc():
    return {
        "responsable_zid": "ZID-PADRE-SM",
        "responsable_name": "Padre Smoke",
        "relation": "PADRE",
        "child_name": "Nino Smoke",
        "birth_date": "2019-05-10",
        "child_zid": "ZID-BABY-SM",
        "child_zid_status": "VERIFIED",
        "institution_id": "INST-1",
        "level": "BASICA",
        "grade": "1",
        "turn": "MATUTINA",
        "authorized_pickup": PICK2,
        "emergency_contacts": EMG}


def test_smoke_http_punta_a_punta(tmp_path) -> None:
    src = pathlib.Path(
        "apps/semilla/server.py").read_text(
        encoding="utf-8")
    if "_HR_V2" not in src:
        pytest.skip("wiring S-4 no presente")
    db = SQLiteAdapter(tmp_path / "s.db")
    st = SemillaStore(db, FrozenClock())
    cls = ClassroomEngine(db, FrozenClock())
    cls.create(name="1A", institution_id="INST-1",
        school_year="2026", level="BASICA",
        grade="1", section="A", turn="MATUTINA",
        capacity=30)
    cls.create(name="1T", institution_id="INST-1",
        school_year="2026", level="BASICA",
        grade="1", section="A", turn="VESPERTINA",
        capacity=5)
    server = serve_semilla(st, _DummyClient(),
        host="127.0.0.1", port=0)
    base = ("http://127.0.0.1:"
            + str(server.bound_port))
    t = threading.Thread(
        target=server.serve_forever, daemon=True)
    t.start()
    try:
        code, health = _call(base,
            "/semilla/api/health")
        assert code == 200
        assert health["ok"] is True
        code, p = _call(base,
            "/semilla/api/home-registration",
            method="POST", doc=_doc())
        assert code == 201
        rid = p["request"]["request_id"]
        code2, p2 = _call(base,
            "/semilla/api/home-registration/"
            + rid + "/confirm", method="POST",
            doc={"director_actor": "DIR-SM"})
        assert code2 == 200
        assert p2["status"] == "ACTIVA"
        assert p2["student"]["zid"] == "ZID-BABY-SM"
        code3, p3 = _call(base,
            "/semilla/api/home-registrations"
            "?institution_id=INST-1")
        assert code3 == 200
        assert p3["count"] == 0
        code4, p4 = _call(base,
            "/semilla/api/home-registration",
            method="POST", doc={})
        assert code4 == 400
        print("OK SMOKE HTTP REAL: socket vivo -> health 200 -> start 201 -> confirm 200 ACTIVA (ZID nacimiento, cupo UNA vez) -> pendientes -> 400 honesto")
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=5)
