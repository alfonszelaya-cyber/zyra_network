import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.student.student_registry_engine import StudentRegistryEngine
from apps.semilla.domain.evaluation.notes_flow_engine import NotesFlowEngine
from apps.semilla.domain.attendance.linked_attendance_engine import LinkedAttendanceEngine
from apps.semilla.domain.education_ai.tutor_link_engine import TutorLinkEngine
from apps.semilla.domain.learning.learning_path_engine import LearningPathEngine

PICK2 = [{"name": "Mama", "relation": "MADRE"},
         {"name": "Papa", "relation": "PADRE"}]
EMG = [{"name": "Tio", "relation": "TIO", "phone": "911"}]

def _base(tmp_path):
    db = SQLiteAdapter(tmp_path / "t.db")
    clock = FrozenClock()
    students = StudentRegistryEngine(db, clock)
    nf = NotesFlowEngine(db, clock,
        evaluation_engine=None, history_engine=None,
        family_engine=None)
    la = LinkedAttendanceEngine(db, clock,
        attendance_engine=None, alert_engine=None)
    tl = TutorLinkEngine(db, clock,
        student_registry=students)
    lp = LearningPathEngine(db, clock, tutor_link=tl)
    return db, clock, students, nf, la, tl, lp

def _alumno(students, name="Alumno Tutoria"):
    return students.register(full_name=name,
        level="BASICA", grade="1", institution_id="INST-1",
        tutores=[{"name": "Mama", "relation": "MADRE",
                  "zid": "ZID-M-1"}],
        authorized_pickup=PICK2,
        emergency_contacts=EMG,
        zid="ZID-" + name[:3], zid_status="PROVISIONAL")

def test_s8_snapshot_integrado(tmp_path) -> None:
    db, clock, students, nf, la, tl, lp = _base(tmp_path)
    est = _alumno(students)
    nf.record_note(student_id=est["student_id"],
        subject="LENGUA", period="P1", score="5.00",
        teacher_id="PROF-L")
    nf.record_note(student_id=est["student_id"],
        subject="MATEMATICAS", period="P1", score="8.50",
        teacher_id="PROF-M")
    la.record_class(student_id=est["student_id"],
        classroom_id="AULA-1", subject="MATEMATICAS",
        date="2026-03-10", status="PRESENTE",
        time_slot="08:00")
    snap = tl.snapshot(est["student_id"])
    assert snap["found"] is True
    assert snap["averages"]["LENGUA"] == "5.00"
    assert snap["averages"]["MATEMATICAS"] == "8.50"
    assert snap["attendance"]["PRESENTE"] == 1
    assert snap["tutor_sessions"] == []
    nf2 = tl.snapshot("NO-EXISTE")
    assert nf2["found"] is False
    print("OK S-8: snapshot consolida expediente + notas (S-9) + asistencia (S-6) + sesiones")

def test_s8_next_objective_peor_materia(tmp_path) -> None:
    db, clock, students, nf, la, tl, lp = _base(tmp_path)
    est = _alumno(students)
    o0 = tl.next_objective(est["student_id"])
    assert o0["subject"] == "GENERAL"
    assert o0["difficulty"] == 1
    assert "sin notas" in o0["reason"]
    nf.record_note(student_id=est["student_id"],
        subject="LENGUA", period="P1", score="5.00")
    nf.record_note(student_id=est["student_id"],
        subject="MATEMATICAS", period="P1", score="8.50")
    o1 = tl.next_objective(est["student_id"])
    assert o1["subject"] == "LENGUA"
    assert o1["difficulty"] == 2
    assert "5.00" in o1["reason"]
    assert "LENGUA" in o1["reason"]
    objs = tl.objectives_of(est["student_id"])
    actives = [o for o in objs
               if o["status"] == "ACTIVO"]
    assert len(actives) == 1
    assert actives[0]["objective_id"] == \
        o1["objective_id"]
    replaced = [o for o in objs
                if o["status"] == "REEMPLAZADO"]
    assert len(replaced) == 1
    assert replaced[0]["subject"] == "GENERAL"
    print("OK S-8: FOCO UNICO — el GENERAL de arranque queda REEMPLAZADO cuando hay notas reales (peor promedio -> LENGUA)")

def test_s8_record_attempt_racha_y_sesion(tmp_path) -> None:
    db, clock, students, nf, la, tl, lp = _base(tmp_path)
    est = _alumno(students)
    nf.record_note(student_id=est["student_id"],
        subject="LENGUA", period="P1", score="5.00")
    o = tl.next_objective(est["student_id"])
    assert o["difficulty"] == 2
    r1 = tl.record_attempt(o["objective_id"],
        correct=True, detail="bien")
    assert r1["difficulty"] == 3
    assert r1["streak"] == 1
    assert r1["objective_status"] == "ACTIVO"
    r2 = tl.record_attempt(o["objective_id"],
        correct=True)
    assert r2["difficulty"] == 4
    assert r2["streak"] == 2
    r3 = tl.record_attempt(o["objective_id"],
        correct=True)
    assert r3["difficulty"] == 5
    assert r3["streak"] == 3
    assert r3["objective_status"] == "COMPLETADO"
    sess = db.query_one(
        "SELECT level, streak, status FROM"
        " sm_tutor_sessions WHERE student_id = ?"
        " AND subject = 'LENGUA' ORDER BY rowid",
        (est["student_id"],))
    assert sess is not None
    assert int(sess["level"]) == 5
    assert int(sess["streak"]) == 3
    assert str(sess["status"]) == "OPEN"
    est2 = _alumno(students, "Ben Dos")
    o2 = tl.next_objective(est2["student_id"])
    rf = tl.record_attempt(o2["objective_id"],
        correct=False)
    assert rf["difficulty"] == 1
    assert rf["streak"] == 0
    print("OK S-8: aciertos suben nivel/racha (racha 3 COMPLETADO) + sesion sm_tutor_sessions sincronizada + error resetea racha sin bajar de 1")

def test_s13_ruta_y_progreso(tmp_path) -> None:
    db, clock, students, nf, la, tl, lp = _base(tmp_path)
    est = _alumno(students)
    nf.record_note(student_id=est["student_id"],
        subject="LENGUA", period="P1", score="5.00")
    nf.record_note(student_id=est["student_id"],
        subject="MATEMATICAS", period="P1", score="8.50")
    p = lp.build_path(est["student_id"])
    assert p["total_steps"] == 6
    assert p["by_subject"]["LENGUA"]["base"] == 2
    assert p["by_subject"]["MATEMATICAS"]["base"] == 3
    assert p["by_subject"]["LENGUA"]["steps"] == [2, 3, 4]
    pr0 = lp.progress(est["student_id"])
    assert pr0["total"] == 6
    assert pr0["completed"] == 0
    assert pr0["pct"] == "0.00"
    assert pr0["next_step"]["subject"] == "LENGUA"
    assert pr0["next_step"]["step_no"] == 1
    first = db.query_one(
        "SELECT path_id FROM sm_learning_paths WHERE"
        " student_id = ? AND subject = 'LENGUA' AND"
        " step_no = 1", (est["student_id"],))
    lp.complete_step(str(first["path_id"]))
    pr1 = lp.progress(est["student_id"])
    assert pr1["completed"] == 1
    assert pr1["pct"] == "16.67"
    assert pr1["next_step"]["subject"] == "LENGUA"
    assert pr1["next_step"]["step_no"] == 2
    print("OK S-13: ruta 3 pasos/materia con base del promedio real + progreso Decimal 2d + siguiente paso ordenado")
    with pytest.raises(KeyError):
        lp.complete_step("NO-EXISTS")

def test_s13_ruta_general_sin_notas(tmp_path) -> None:
    db, clock, students, nf, la, tl, lp = _base(tmp_path)
    est = _alumno(students, "Sin Notas")
    p = lp.build_path(est["student_id"])
    assert p["total_steps"] == 3
    assert "GENERAL" in p["by_subject"]
    assert p["by_subject"]["GENERAL"]["base"] == 1
    assert "sin notas" in p["note"]
    print("OK S-13 honesto (regla 66): alumno sin notas -> ruta GENERAL nivel 1 con nota aclaratoria")
