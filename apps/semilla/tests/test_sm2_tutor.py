import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.education_ai.tutor_core_engine import TutorCoreEngine
from apps.semilla.domain.education_ai.teacher_insights_engine import TeacherInsightsEngine
from apps.semilla.domain.curriculum.curriculum_engine import CurriculumEngine

def test_tutor_corazon_integridad(tmp_path) -> None:
    t = TutorCoreEngine(SQLiteAdapter(tmp_path / "t.db"),
                        FrozenClock())
    s = t.start_session(student_id="STU-T",
        subject="Matematica", mode="TUTOR")
    h1 = t.hint(mode="TUTOR", hints_used=0,
                solution_hint="suma las decenas primero")
    assert h1["allowed"] is True
    assert "metodo" in h1["integrity"]
    h2 = t.hint(mode="EXAM", hints_used=0,
                solution_hint="x")
    assert h2["allowed"] is False
    h3 = t.hint(mode="TUTOR", hints_used=3,
                solution_hint="x")
    assert h3["allowed"] is False
    a1 = t.record_attempt(session_id=s["session_id"],
        challenge="7+5", student_answer="12",
        correct=True, hints_used=1)
    assert a1["points"] == 8
    s2 = t.get_session(s["session_id"])
    assert s2["level"] == 2 and s2["streak"] == 1
    a2 = t.record_attempt(session_id=s["session_id"],
        challenge="9+8", student_answer="15",
        correct=False)
    s3 = t.get_session(s["session_id"])
    assert s3["level"] == 1 and s3["streak"] == 0
    assert t.session_points(s["session_id"]) == 8
    t.close_session(s["session_id"])
    with pytest.raises(ValueError):
        t.record_attempt(session_id=s["session_id"],
            challenge="x", student_answer="y",
            correct=True)
    print("OK tutor corazon: explica sin resolver + examen bloqueado + dificultad")

def test_tutor_ensena_al_maestro(tmp_path) -> None:
    from apps.semilla.domain.evaluation.evaluation_engine import EvaluationEngine
    from apps.semilla.domain.attendance.attendance_engine import AttendanceEngine
    ev = EvaluationEngine(
        SQLiteAdapter(tmp_path / "ev.db"), FrozenClock())
    at = AttendanceEngine(
        SQLiteAdapter(tmp_path / "at.db"), FrozenClock())
    for _ in range(3):
        ev.register(student_id="STU-A",
            subject="Matematica", period="P1",
            score="4.0", teacher_id="TEA-1")
    ev.register(student_id="STU-B", subject="Matematica",
        period="P1", score="9.5", teacher_id="TEA-1")
    at.record(student_id="STU-A", date="2026-03-01",
              status="AUSENTE")
    at.record(student_id="STU-A", date="2026-03-02",
              status="AUSENTE")
    ins = TeacherInsightsEngine(ev, at)
    rep = ins.group_report(["STU-A", "STU-B"],
                           subject="Matematica")
    assert rep["group_size"] == 2
    assert len(rep["at_risk"]) == 1
    assert rep["at_risk"][0]["student_id"] == "STU-A"
    assert (rep["at_risk"][0]["flags"]
            == ["bajo promedio",
                "baja asistencia"])
    assert ("acompanamiento"
            in rep["at_risk"][0]["sugerencia"])
    summ = ins.class_summary(["STU-A", "STU-B"],
                             subject="Matematica")
    assert summ["at_risk_count"] == 1
    print("OK tutor ensena al maestro: STU-A doble riesgo real (promedio+asistencia), STU-B sin datos NO es falso positivo")

def test_evaluaciones_decimal_y_escala(tmp_path) -> None:
    from apps.semilla.domain.evaluation.evaluation_engine import EvaluationEngine
    ev = EvaluationEngine(
        SQLiteAdapter(tmp_path / "e2.db"), FrozenClock())
    ev.register(student_id="STU-E", subject="Matematica",
        period="P1", score="9.567", teacher_id="TEA-1")
    assert (ev.average_of("STU-E",
        subject="Matematica")["average"] == "9.57")
    with pytest.raises(ValueError):
        ev.register(student_id="STU-E", subject="X",
            period="P1", score="11")
    with pytest.raises(ValueError):
        ev.register(student_id="STU-E", subject="X",
            period="P1", score="-1")
    print("OK evaluaciones: Decimal 2d HALF_UP + escala 0-10")

def test_curriculo_mined_plantilla(tmp_path) -> None:
    cur = CurriculumEngine(
        SQLiteAdapter(tmp_path / "cu.db"), FrozenClock())
    r = cur.install_template()
    assert r["subjects_created"] == 91
    bas = cur.subjects_of("BASICA", "3")
    names = [x["subject"] for x in bas]
    assert "Matematica" in names and "Lenguaje" in names
    par = cur.subjects_of("PARVULARIA", "Kinder")
    assert len(par) == 4
    med = cur.subjects_of("MEDIA", "1 Bachillerato")
    assert len(med) == 8
    print("OK curriculo: 91 materias exactas en 3 niveles")
