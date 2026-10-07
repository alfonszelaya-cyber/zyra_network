import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.student.student_registry_engine import StudentRegistryEngine
from apps.semilla.domain.classroom.classroom_engine import ClassroomEngine
from apps.semilla.domain.academic.enrollment_engine import EnrollmentEngine
from apps.semilla.domain.student.role_dashboards_engine import RoleDashboardsEngine

PICK2 = [{"name": "Mama", "relation": "MADRE"},
         {"name": "Papa", "relation": "PADRE"}]

def _setup(tmp_path):
    db = SQLiteAdapter(tmp_path / "s.db")
    clock = FrozenClock()
    students = StudentRegistryEngine(db, clock)
    cls = ClassroomEngine(db, clock)
    en = EnrollmentEngine(db, clock, classroom_engine=cls)
    dash = RoleDashboardsEngine(db, clock,
        student_registry=students,
        classroom_engine=cls, enrollment_engine=en)
    return students, cls, en, dash

def test_director_cupos_exactos(tmp_path) -> None:
    students, cls, en, dash = _setup(tmp_path)
    a1 = cls.create(name="1A-M", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="MATUTINA", capacity=30)
    a2 = cls.create(name="1A-T", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="VESPERTINA", capacity=25)
    en.enroll(student_id="ALU-1",
        classroom_id=a1["classroom_id"],
        school_year="2026")
    en.enroll(student_id="ALU-2",
        classroom_id=a1["classroom_id"],
        school_year="2026")
    en.enroll(student_id="ALU-3",
        classroom_id=a2["classroom_id"],
        school_year="2026")
    d = dash.director_dashboard(institution_id="INST-1",
        school_year="2026")
    assert d["role"] == "DIRECTOR"
    assert d["aulas"] == 2
    assert d["total_capacity"] == 55
    assert d["total_enrolled"] == 3
    assert d["total_cupos"] == 52
    assert set(d["grados"]) == {"1"}
    assert set(d["turnos"]) == {"MATUTINA", "VESPERTINA"}
    f1 = [r for r in d["classroom_rows"]
          if r["classroom_id"] == a1["classroom_id"]][0]
    assert f1["capacity"] == 30
    assert f1["enrolled"] == 2
    assert f1["cupos"] == 28
    assert len(d["plan_de_llenado"]) == 2
    print("OK director: aulas/capacidad/matriculados/cupos REALES")

def test_student_dashboard_degrada_sin_motores(tmp_path) -> None:
    students, cls, en, dash = _setup(tmp_path)
    est = students.register(full_name="Nina Prueba",
        level="BASICA", grade="1",
        institution_id="INST-1",
        tutores=[{"name": "Mama", "relation": "MADRE",
                  "zid": "ZID-M-1"}],
        authorized_pickup=PICK2,
        emergency_contacts=[{"name": "Tio",
                             "relation": "TIO",
                             "phone": "911"}],
        zid="ZID-NINA-1", zid_status="PROVISIONAL")
    d = dash.student_dashboard(est["student_id"])
    assert d["found"] is True
    assert d["student"]["student_id"] == est["student_id"]
    assert d["average"] is None
    assert d["attendance_pct"] is None
    nf = dash.student_dashboard("NO-EXISTE")
    assert nf["found"] is False
    print("OK alumno: SU cuadro con sus datos; degradacion segura sin motores opcionales (SE-3 respetado: 2 encargados retiro)")

def test_ministry_departamento_municipio_plan(tmp_path) -> None:
    students, cls, en, dash = _setup(tmp_path)
    a1 = cls.create(name="C-1A", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="MATUTINA", capacity=30)
    a2 = cls.create(name="N-2A", institution_id="INST-8",
        school_year="2026", level="BASICA", grade="2",
        section="A", turn="VESPERTINA", capacity=10)
    dash.set_school_geo(institution_id="INST-1",
        name="Escuela Centro",
        department="LA_LIBERTAD",
        municipality="SAN_SALVADOR")
    dash.set_school_geo(institution_id="INST-8",
        name="Escuela Norte",
        department="CHALATENANGO",
        municipality="LA_PALMA")
    m = dash.ministry_dashboard()
    assert m["role"] == "MINISTRY"
    assert m["total_escuelas"] == 2
    assert m["total_capacidad"] == 40
    assert m["total_cupos"] == 40
    ml = dash.ministry_dashboard(
        department="LA_LIBERTAD")
    assert ml["total_escuelas"] == 1
    assert ml["escuelas"][0]["nombre"] == "Escuela Centro"
    mm = dash.ministry_dashboard(
        municipality="LA_PALMA")
    assert mm["total_escuelas"] == 1
    assert mm["escuelas"][0]["institution_id"] == "INST-8"
    plan = m["plan_de_llenado"]
    assert len(plan) == 2
    assert plan[0]["cupos"] == 30
    print("OK ministerio: escuelas por depto/municipio, capacidad, turnos y plan de llenado")

def test_s3_guard_capacidad_exacta(tmp_path) -> None:
    students, cls, en, dash = _setup(tmp_path)
    chico = cls.create(name="S-3", institution_id="INST-9",
        school_year="2026", level="BASICA", grade="3",
        section="A", turn="MATUTINA", capacity=1)
    cid = chico["classroom_id"]
    assert dash.capacity_state(cid)["cupos"] == 1
    dash.guard_capacity(cid, requesting=1)
    en.enroll(student_id="ALU-X", classroom_id=cid,
        school_year="2026")
    st = dash.capacity_state(cid)
    assert st["lleno"] is True
    assert st["cupos"] == 0
    with pytest.raises(ValueError):
        dash.guard_capacity(cid, requesting=1)
    print("OK S-3: capacidad exacta protegida — jamas se pide cupo que no existe")
