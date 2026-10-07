import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.student.student_registry_engine import StudentRegistryEngine
from apps.semilla.domain.classroom.classroom_engine import ClassroomEngine
from apps.semilla.domain.academic.enrollment_engine import EnrollmentEngine
from apps.semilla.domain.academic.auto_assignment_engine import AutoAssignmentEngine

PICK2 = [{"name": "Mama", "relation": "MADRE"},
         {"name": "Papa", "relation": "PADRE"}]
EMG = [{"name": "Tio", "relation": "TIO", "phone": "911"}]

def _env(tmp_path):
    db = SQLiteAdapter(tmp_path / "a.db")
    clock = FrozenClock()
    students = StudentRegistryEngine(db, clock)
    cls = ClassroomEngine(db, clock)
    en = EnrollmentEngine(db, clock, classroom_engine=cls)
    s7 = AutoAssignmentEngine(db, clock,
        student_registry=students,
        classroom_engine=cls, enrollment_engine=en)
    return db, students, cls, en, s7

def _alumno(students, **over):
    kw = {"full_name": "Alumno S7", "level": "BASICA",
          "grade": "1", "institution_id": "",
          "tutores": [{"name": "Mama",
                       "relation": "MADRE",
                       "zid": "ZID-M-7"}],
          "authorized_pickup": PICK2,
          "emergency_contacts": EMG,
          "zid": "ZID-S7", "zid_status": "PROVISIONAL"}
    kw.update(over)
    return students.register(**kw)

def test_asigna_escuela_indicada_preferencia_turno(tmp_path) -> None:
    db, students, cls, en, s7 = _env(tmp_path)
    am = cls.create(name="1A", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="MATUTINA", capacity=2)
    at = cls.create(name="1T", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="VESPERTINA", capacity=5)
    est = _alumno(students)
    r = s7.assign(student_id=est["student_id"],
        level="BASICA", grade="1")
    assert r["status"] == "ASIGNADO"
    assert r["turn"] == "MATUTINA"
    assert r["classroom_id"] == am["classroom_id"]
    assert cls.get(am["classroom_id"])["enrolled"] == 1
    assert cls.get(at["classroom_id"])["enrolled"] == 0
    pv = s7.preview(student_id=est["student_id"],
        level="BASICA", grade="1")
    assert any(p["turnos_con_cupo"] == ["MATUTINA",
               "VESPERTINA"] for p in pv["plan"])
    print("OK S-7: asigna en la escuela indicada, preferencia MATUTINA primero, cupo contado UNA vez, preview sin enrollar")

def test_respeta_expediente_del_alumno(tmp_path) -> None:
    db, students, cls, en, s7 = _env(tmp_path)
    a1 = cls.create(name="1A-A", institution_id="INST-A",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="MATUTINA", capacity=1)
    b1 = cls.create(name="1B-B", institution_id="INST-B",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="MATUTINA", capacity=30)
    est = _alumno(students, institution_id="INST-A")
    r = s7.assign(student_id=est["student_id"],
        level="BASICA", grade="1")
    assert r["status"] == "ASIGNADO"
    assert r["institution_id"] == "INST-A"
    assert cls.get(b1["classroom_id"])["enrolled"] == 0
    print("OK S-7: la escuela del expediente manda aunque otra tenga mas cupo")

def test_descubre_escuela_con_cupo(tmp_path) -> None:
    db, students, cls, en, s7 = _env(tmp_path)
    b1 = cls.create(name="2B", institution_id="INST-B",
        school_year="2026", level="BASICA", grade="2",
        section="A", turn="VESPERTINA", capacity=3)
    est = _alumno(students)
    r = s7.assign(student_id=est["student_id"],
        level="BASICA", grade="2",
        turn_order=["MATUTINA", "VESPERTINA"])
    assert r["status"] == "ASIGNADO"
    assert r["institution_id"] == "INST-B"
    assert r["turn"] == "VESPERTINA"
    print("OK S-7: sin escuela indicada DESCUBRE la que tiene cupo real y respeta el orden de turnos")

def test_no_cupos_honesto(tmp_path) -> None:
    db, students, cls, en, s7 = _env(tmp_path)
    a1 = cls.create(name="3A", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="3",
        section="A", turn="MATUTINA", capacity=1)
    en.enroll(student_id="OTRO-X",
        classroom_id=a1["classroom_id"],
        school_year="2026")
    est = _alumno(students)
    r = s7.assign(student_id=est["student_id"],
        level="BASICA", grade="3")
    assert r["status"] == "NO_CUPOS"
    assert "MATUTINA" in r["note"]
    assert r["tried"][0]["turnos_con_cupo"] == []
    assert cls.get(a1["classroom_id"])["enrolled"] == 1
    print("OK S-7 honesto (regla 66): aula llena -> NO_CUPOS con nota clara, jamas inventa cupo")
