import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.classroom.classroom_engine import ClassroomEngine
from apps.semilla.infrastructure.persistence.semilla_store import SemillaStore
from apps.semilla.routers.student.home_registration_router import (
    HomeRegistrationRouter, patch_hr_routes)

PICK2 = [{"name": "Mama", "relation": "MADRE"},
         {"name": "Papa", "relation": "PADRE"}]
EMG = [{"name": "Tio", "relation": "TIO", "phone": "911"}]

def _env(tmp_path, cap_m=30, cap_t=5):
    db = SQLiteAdapter(tmp_path / "r.db")
    clock = FrozenClock()
    cls = ClassroomEngine(db, clock)
    man = cls.create(name="1A", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="MATUTINA", capacity=cap_m)
    tar = cls.create(name="1T", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="VESPERTINA", capacity=cap_t)
    r = HomeRegistrationRouter(db, clock)
    return db, cls, man, tar, r

def _doc(**over):
    base = {"responsable_zid": "ZID-PADRE-1",
        "responsable_name": "Padre Perez",
        "relation": "PADRE", "child_name": "Nino HTTP",
        "birth_date": "2019-05-10",
        "child_zid": "ZID-BABY-9",
        "child_zid_status": "VERIFIED",
        "institution_id": "INST-1", "level": "BASICA",
        "grade": "1", "turn": "MATUTINA",
        "authorized_pickup": PICK2,
        "emergency_contacts": EMG}
    base.update(over)
    return base

def test_flujo_completo(tmp_path) -> None:
    db, cls, man, tar, r = _env(tmp_path)
    code, p = r.dispatch(method="POST",
        segs=["home-registration"], doc=_doc())
    assert code == 201 and p["ok"] is True
    rid = p["request"]["request_id"]
    code2, p2 = r.dispatch(method="POST",
        segs=["home-registration", rid, "confirm"],
        doc={"director_actor": "DIR-1"})
    assert code2 == 200 and p2["status"] == "ACTIVA"
    assert p2["student"]["zid"] == "ZID-BABY-9"
    assert p2["student"]["zid_status"] == "VERIFIED"
    assert p2["student"]["tutores"][0]["zid"] == "ZID-PADRE-1"
    assert cls.get(man["classroom_id"])["enrolled"] == 1
    code3, p3 = r.dispatch(method="GET",
        segs=["home-registration", rid])
    assert code3 == 200
    assert p3["request"]["status"] == "ACTIVA"
    code4, p4 = r.dispatch(method="GET",
        segs=["home-registrations"],
        query={"institution_id": ["INST-1"]})
    assert code4 == 200 and p4["count"] == 0
    print("OK flujo: start 201 -> confirm 200 ACTIVA -> ZID nacimiento (regla 78) -> cupo UNA vez -> detalle -> pendientes")

def test_sin_cupos_409_alternativas(tmp_path) -> None:
    db, cls, man, tar, r = _env(tmp_path, cap_m=1, cap_t=5)
    code, p = r.dispatch(method="POST",
        segs=["home-registration"],
        doc=_doc(child_zid="", child_zid_status="NONE"))
    assert code == 201
    rid = p["request"]["request_id"]
    r.dispatch(method="POST",
        segs=["home-registration", rid, "confirm"],
        doc={"director_actor": "D"})
    code2, p2 = r.dispatch(method="POST",
        segs=["home-registration"],
        doc=_doc(responsable_zid="ZID-2",
                 child_name="Segundo", child_zid="",
                 child_zid_status="NONE"))
    assert code2 == 409
    assert "MATUTINA COMPLETADA" in p2["note"]
    assert "VESPERTINA" in p2["note"]
    code3, p3 = r.dispatch(method="POST",
        segs=["home-registration"],
        doc=_doc(responsable_zid="ZID-3",
                 child_name="Tercero", child_zid="",
                 child_zid_status="NONE",
                 turn="VESPERTINA"))
    assert code3 == 201
    rid3 = p3["request"]["request_id"]
    code4, p4 = r.dispatch(method="POST",
        segs=["home-registration", rid3, "confirm"],
        doc={"director_actor": "D"})
    assert code4 == 200
    assert p4["enrollment"]["turn"] == "VESPERTINA"
    print("OK SIN_CUPOS: 409 con alternativas y la tarde SI recibe")

def test_escuela_sin_aulas_409_honesto(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "v.db")
    r = HomeRegistrationRouter(db, FrozenClock())
    code, p = r.dispatch(method="POST",
        segs=["home-registration"], doc=_doc())
    assert code == 409
    assert "Sin cupos" in p["note"]
    print("OK honesto (regla 66): escuela SIN aulas configuradas -> 409 SIN_CUPOS, jamas se inventa capacidad (esto es lo que el patch test piso sin querer: le faltaba crear aulas)")

def test_errores_honestos(tmp_path) -> None:
    db, cls, man, tar, r = _env(tmp_path)
    code, p = r.dispatch(method="POST",
        segs=["home-registration"],
        doc=_doc(responsable_zid=""))
    assert code == 400
    assert "faltan campos" in p["error"]
    code2, p2 = r.dispatch(method="POST",
        segs=["home-registration"],
        doc=_doc(relation="PRIMO"))
    assert code2 == 400
    code3, p3 = r.dispatch(method="POST",
        segs=["home-registration"],
        doc=_doc(authorized_pickup=PICK2[:1]))
    assert code3 == 400 and "retiro" in p3["error"]
    code4, p4 = r.dispatch(method="POST",
        segs=["home-registration"], doc=None)
    assert code4 == 400
    code5, p5 = r.dispatch(method="GET",
        segs=["home-registration", "NO-EXISTS"])
    assert code5 == 404
    code6, p6 = r.dispatch(method="GET",
        segs=["home-registration"])
    assert code6 == 405
    code7, p7 = r.dispatch(method="GET",
        segs=["otra-cosa"])
    assert code7 == 404
    print("OK honesto: 400 faltantes/SE-3/body, 404, 405")

def test_patch_server_real(tmp_path) -> None:
    import apps.semilla.server as srv
    db = SQLiteAdapter(tmp_path / "w.db")
    st = SemillaStore(db, FrozenClock())
    cls = ClassroomEngine(db, FrozenClock())
    man = cls.create(name="1A-W", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="MATUTINA", capacity=30)
    tar = cls.create(name="1T-W", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="VESPERTINA", capacity=5)
    patch_hr_routes()
    patch_hr_routes()
    assert getattr(srv.SemillaApiHandler,
                   "_HR_V2", False) is True
    h = object.__new__(srv.SemillaApiHandler)
    h.store = st
    h.path = "/semilla/api/home-registration"
    assert srv.SemillaApiHandler._hr_wants(h) is True
    h.path = ("/semilla/api/home-registrations"
              "?institution_id=INST-1")
    assert srv.SemillaApiHandler._hr_wants(h) is True
    h.path = "/api/home-registration"
    assert srv.SemillaApiHandler._hr_wants(h) is True
    h.path = "/semilla/api/profile/ACC-1"
    assert srv.SemillaApiHandler._hr_wants(h) is False
    h.path = "/semilla/api/health"
    assert srv.SemillaApiHandler._hr_wants(h) is False
    h.path = "/semilla/register"
    assert srv.SemillaApiHandler._hr_wants(h) is False
    h.path = "/semilla/api/home-registration"
    code, p = srv.SemillaApiHandler._hr_compute(
        h, _doc(), "POST")
    assert code == 201
    rid = p["request"]["request_id"]
    h.path = ("/semilla/api/home-registration/"
              + rid + "/confirm")
    code2, p2 = srv.SemillaApiHandler._hr_compute(
        h, {"director_actor": "DIR-9"}, "POST")
    assert code2 == 200
    assert p2["status"] == "ACTIVA"
    assert cls.get(man["classroom_id"])["enrolled"] == 1
    h.path = ("/semilla/api/home-registrations"
              "?institution_id=INST-1")
    code3, p3 = srv.SemillaApiHandler._hr_compute(
        h, None, "GET")
    assert code3 == 200 and p3["count"] == 0
    h2 = object.__new__(srv.SemillaApiHandler)
    h2.store = None
    h2.path = "/semilla/api/home-registration"
    code4, p4 = srv.SemillaApiHandler._hr_compute(
        h2, _doc(), "POST")
    assert code4 == 503
    print("OK patch REAL: aulas creadas en la db del store -> start 201 -> confirm 200 (cupo UNA vez) -> pendientes -> 503 honesto sin store; cache del router pegado al store (sin id() global)")
