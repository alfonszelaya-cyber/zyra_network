import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.student.student_registry_engine import StudentRegistryEngine
from apps.semilla.domain.classroom.classroom_engine import ClassroomEngine
from apps.semilla.domain.academic.enrollment_engine import EnrollmentEngine
from apps.semilla.domain.student.home_registration_engine import HomeRegistrationEngine

PICK = [{"name": "Tia Maria", "relation": "TIA", "phone": "7777-1111"},
        {"name": "Abuelo Jose", "relation": "ABUELO", "phone": "7777-2222"}]
EMG = [{"name": "Mama Lopez", "relation": "MADRE", "phone": "911"}]

def _setup(tmp_path):
    db = SQLiteAdapter(tmp_path / "s.db")
    clock = FrozenClock()
    students = StudentRegistryEngine(db, clock)
    cls = ClassroomEngine(db, clock)
    man = cls.create(name="1A-M", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="MATUTINA", capacity=30)
    tar = cls.create(name="1A-T", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="VESPERTINA", capacity=30)
    en = EnrollmentEngine(db, clock, classroom_engine=cls)
    home = HomeRegistrationEngine(db, clock,
        student_registry=students, classroom_engine=cls,
        enrollment_engine=en)
    return home, cls, en

def test_flujo_completo_con_zid_nacimiento(tmp_path) -> None:
    home, cls, en = _setup(tmp_path)
    r = home.start_request(
        responsable_zid="ZID-PADRE-1",
        responsable_name="Padre Perez",
        relation="PADRE", child_name="Nino Nuevo",
        birth_date="2019-05-10",
        child_zid="ZID-BABY-1",
        child_zid_status="VERIFIED",
        institution_id="INST-1", level="BASICA",
        grade="1", turn="MATUTINA",
        authorized_pickup=PICK, emergency_contacts=EMG)
    assert r["status"] == "PENDING_ESCUELA"
    assert r["child_zid"] == "ZID-BABY-1"
    conf = home.confirm_by_school(
        r["request_id"], director_actor="DIR-1")
    assert conf["status"] == "ACTIVA"
    est = conf["student"]
    assert est["zid"] == "ZID-BABY-1"
    assert est["zid_status"] == "VERIFIED"
    assert est["tutores"][0]["zid"] == "ZID-PADRE-1"
    assert len(est["authorized_pickup"]) == 2
    assert (cls.get(r["classroom_id"])["enrolled"]) == 1
    print("OK flujo: ZID de nacimiento (regla 78) + formulario completo + CUPO CONTADO UNA VEZ")

def test_sin_documentos_no_impide(tmp_path) -> None:
    home, cls, en = _setup(tmp_path)
    r = home.start_request(
        responsable_zid="ZID-PADRE-2",
        responsable_name="Madre Gomez",
        relation="MADRE", child_name="Menor Sin Docs",
        institution_id="INST-1", level="BASICA",
        grade="1", turn="MATUTINA",
        authorized_pickup=PICK, emergency_contacts=EMG)
    assert r["status"] == "PENDING_ESCUELA"
    assert r["child_zid"] == ""
    conf = home.confirm_by_school(
        r["request_id"], director_actor="DIR-1")
    est = conf["student"]
    assert est["zid"] == ""
    assert est["zid_status"] == "NONE"
    print("OK sin documentos: NO impide matricula (MINED) — zid pendiente")

def test_validaciones_formulario(tmp_path) -> None:
    home, cls, en = _setup(tmp_path)
    with pytest.raises(ValueError):
        home.start_request(responsable_zid="",
            responsable_name="X", relation="PADRE",
            child_name="Y", institution_id="INST-1",
            level="BASICA", grade="1",
            authorized_pickup=PICK, emergency_contacts=EMG)
    with pytest.raises(ValueError):
        home.start_request(responsable_zid="ZID-R",
            responsable_name="X", relation="PRIMO",
            child_name="Y", institution_id="INST-1",
            level="BASICA", grade="1",
            authorized_pickup=PICK, emergency_contacts=EMG)
    with pytest.raises(ValueError):
        home.start_request(responsable_zid="ZID-R",
            responsable_name="X", relation="PADRE",
            child_name="Y", institution_id="INST-1",
            level="BASICA", grade="1",
            authorized_pickup=PICK[:1],
            emergency_contacts=EMG)
    with pytest.raises(ValueError):
        home.start_request(responsable_zid="ZID-R",
            responsable_name="X", relation="PADRE",
            child_name="Y", institution_id="INST-1",
            level="BASICA", grade="1",
            authorized_pickup=PICK, emergency_contacts=[])
    print("OK validaciones: responsable+relation+2 encargados+emergencia (SE-3)")

def test_turno_lleno_sin_cupos_con_alternativas(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "s2.db")
    clock = FrozenClock()
    students = StudentRegistryEngine(db, clock)
    cls = ClassroomEngine(db, clock)
    lleno = cls.create(name="LLENA-M", institution_id="INST-8",
        school_year="2026", level="BASICA", grade="2",
        section="A", turn="MATUTINA", capacity=1)
    tar = cls.create(name="LIBRE-T", institution_id="INST-8",
        school_year="2026", level="BASICA", grade="2",
        section="A", turn="VESPERTINA", capacity=5)
    en = EnrollmentEngine(db, clock, classroom_engine=cls)
    en.enroll(student_id="OTRO-1",
        classroom_id=lleno["classroom_id"],
        school_year="2026")
    home = HomeRegistrationEngine(db, clock,
        student_registry=students, classroom_engine=cls,
        enrollment_engine=en)
    r = home.start_request(responsable_zid="ZID-R2",
        responsable_name="Alguien", relation="PADRE",
        child_name="Z", institution_id="INST-8",
        level="BASICA", grade="2", turn="MATUTINA",
        authorized_pickup=PICK, emergency_contacts=EMG)
    assert r["status"] == "SIN_CUPOS"
    assert "MATUTINA COMPLETADA" in r["note"]
    assert "VESPERTINA" in r["note"]
    with pytest.raises(ValueError):
        home.confirm_by_school(r["request_id"],
            director_actor="DIR-8")
    r2 = home.start_request(responsable_zid="ZID-R3",
        responsable_name="Otro", relation="MADRE",
        child_name="W", institution_id="INST-8",
        level="BASICA", grade="2", turn="VESPERTINA",
        authorized_pickup=PICK, emergency_contacts=EMG)
    assert r2["status"] == "PENDING_ESCUELA"
    conf = home.confirm_by_school(r2["request_id"],
        director_actor="DIR-8")
    assert conf["enrollment"]["turn"] == "VESPERTINA"
    pend = home.pending_requests("INST-8")
    assert len(pend) == 0
    print("OK turno lleno: SIN_CUPOS + nota 'solo cupo por la tarde' + la tarde SI recibe")
