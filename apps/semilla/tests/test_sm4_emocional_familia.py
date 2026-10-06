import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.psychology.emotional_monitoring_engine import EmotionalMonitoringEngine
from apps.semilla.domain.psychology.psychology_engine import PsychologyEngine
from apps.semilla.domain.family.family_engine import FamilyEngine
from apps.semilla.domain.analytics.dropout_prediction_engine import DropoutPredictionEngine
from apps.semilla.domain.academic.calendar_engine import CalendarEngine
from apps.semilla.domain.notifications.alert_engine import AlertEngine
from apps.semilla.domain.evaluation.evaluation_engine import EvaluationEngine
from apps.semilla.domain.attendance.attendance_engine import AttendanceEngine
from apps.semilla.application.analytics_use_cases.assess_dropout_use_case import AssessDropoutUseCase

def test_emocional_alerta_y_escalada_critica(tmp_path) -> None:
    al = AlertEngine(SQLiteAdapter(tmp_path / "a.db"),
                     FrozenClock())
    em = EmotionalMonitoringEngine(
        SQLiteAdapter(tmp_path / "e.db"), FrozenClock(),
        alert_engine=al)
    r1 = em.record_mood(student_id="STU-E", mood="feliz")
    assert r1["level"] == "NORMAL"
    assert r1["parent_notified"] is False
    r2 = em.record_mood(student_id="STU-E", mood="triste")
    assert r2["level"] == "ALERT"
    assert r2["parent_notified"] is True
    with pytest.raises(ValueError):
        em.record_mood(student_id="STU-E",
                       mood="estado-falso")
    em.record_mood(student_id="STU-E", mood="estresado")
    r4 = em.record_mood(student_id="STU-E", mood="frustrado")
    assert r4["level"] == "CRITICAL"
    assert r4["escalated"] is True
    tipos = [x["alert_type"] for x in al.unread("STU-E")]
    assert "HEALTH" in tipos
    st = em.emotional_state("STU-E")
    assert st["current_level"] == "CRITICAL"
    assert st["recent_alerts"] >= 3
    hist = em.history_of("STU-E")
    assert hist[0]["mood"] == "feliz"
    assert hist[-1]["level"] == "CRITICAL"
    print("OK emocional: escalada CRITICA + orden rowid determinista")

def test_psicologia_sesiones_y_derivacion(tmp_path) -> None:
    psy = PsychologyEngine(
        SQLiteAdapter(tmp_path / "p.db"), FrozenClock())
    s = psy.schedule_session(student_id="STU-P",
        psychologist="Lic. Martinez",
        scheduled_date="2026-04-10", reason="seguimiento")
    assert s["status"] == "SCHEDULED"
    c = psy.record_session(session_id=s["session_id"],
        notes="sesion inicial positiva",
        followup="revisar en 2 semanas")
    assert c["status"] == "COMPLETED"
    ref = psy.refer_external(student_id="STU-P",
        institution="Clinica del Nino",
        reason="evaluacion especializada")
    assert ref["status"] == "REFERRED"
    print("OK psicologia: sesion + derivacion externa")

def test_familia_consentimientos_comunicacion(tmp_path) -> None:
    fa = FamilyEngine(SQLiteAdapter(tmp_path / "f.db"),
                      FrozenClock())
    assert (fa.check_consent("STU-F",
        "DATA_PROCESSING") is False)
    fa.grant_consent(student_id="STU-F",
        consent_type="DATA_PROCESSING",
        granted_by="PADRE")
    assert (fa.check_consent("STU-F",
        "DATA_PROCESSING") is True)
    fa.revoke_consent(student_id="STU-F",
        consent_type="DATA_PROCESSING",
        revoked_by="PADRE")
    assert (fa.check_consent("STU-F",
        "DATA_PROCESSING") is False)
    fa.grant_consent(student_id="STU-F",
        consent_type="DATA_PROCESSING",
        granted_by="MADRE")
    assert (fa.check_consent("STU-F",
        "DATA_PROCESSING") is True)
    cm = fa.send_communication(student_id="STU-F",
        from_role="TEACHER",
        subject="Reunion de padres", body="jueves 5pm")
    assert cm["status"] == "SENT"
    mt = fa.schedule_meeting(student_id="STU-F",
        date="2026-04-05", topic="rendimiento")
    assert mt["status"] == "SCHEDULED"
    print("OK familia: consentimiento rowid (mas reciente manda) + comunicacion + reunion")

def test_dropout_prediction_riesgos(tmp_path) -> None:
    at = AttendanceEngine(
        SQLiteAdapter(tmp_path / "at.db"), FrozenClock())
    ev = EvaluationEngine(
        SQLiteAdapter(tmp_path / "ev.db"), FrozenClock())
    al = AlertEngine(SQLiteAdapter(tmp_path / "a.db"),
                     FrozenClock())
    em = EmotionalMonitoringEngine(
        SQLiteAdapter(tmp_path / "e.db"), FrozenClock(),
        alert_engine=al)
    dp = DropoutPredictionEngine(at, ev, em)
    uc = AssessDropoutUseCase(dp)
    at.record(student_id="STU-R", date="2026-03-01",
        status="AUSENTE")
    at.record(student_id="STU-R", date="2026-03-02",
        status="AUSENTE")
    ev.register(student_id="STU-R", subject="X",
        period="P1", score="4.0")
    em.record_mood(student_id="STU-R", mood="triste")
    r = uc.execute(student_id="STU-R")
    assert r["risk_level"] == "HIGH"
    assert "asistencia critica (0.0%)" in r["factors"]
    assert "promedio critico (4.0)" in r["factors"]
    ev.register(student_id="STU-OK", subject="X",
        period="P1", score="9.5")
    at.record(student_id="STU-OK", date="2026-03-01",
        status="PRESENTE")
    em.record_mood(student_id="STU-OK", mood="motivado")
    r2 = uc.execute(student_id="STU-OK")
    assert r2["risk_level"] == "LOW"
    r3 = uc.execute(student_id="STU-NADIE")
    assert r3["risk_level"] == "INSUFFICIENT_DATA"
    print("OK dropout: HIGH + LOW + sin datos (informativo regla 57)")

def test_calendario_examenes_alerta(tmp_path) -> None:
    al = AlertEngine(SQLiteAdapter(tmp_path / "a2.db"),
                     FrozenClock())
    cal = CalendarEngine(
        SQLiteAdapter(tmp_path / "cal.db"), FrozenClock(),
        alert_engine=al)
    cal.add_event(date="2026-05-18", event_type="EXAM",
        title="Examen de Ciencias", subject="Ciencias")
    cal.add_event(date="2026-05-20", event_type="HOLIDAY",
        title="Dia del estudiante")
    cal.add_event(date="2026-06-30", event_type="EXAM",
        title="Lejos", subject="X")
    up = cal.upcoming(from_date="2026-05-15", days=7)
    assert len(up) == 2
    n = cal.publish_exam_alerts(from_date="2026-05-15",
        days=7)
    assert n == 1
    alerts = al.alerts_of("*")
    assert alerts[0]["alert_type"] == "EXAM_UPCOMING"
    with pytest.raises(ValueError):
        cal.add_event(date="2026-05-18",
            event_type="FIESTA", title="x")
    print("OK calendario: examenes -> alerta EXAM_UPCOMING + tipo invalido")
