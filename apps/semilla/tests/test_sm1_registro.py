import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.student.student_registry_engine import StudentRegistryEngine
from apps.semilla.domain.classroom.classroom_engine import ClassroomEngine
from apps.semilla.domain.academic.enrollment_engine import EnrollmentEngine
from apps.semilla.domain.notifications.alert_engine import AlertEngine
from apps.semilla.domain.notifications.incident_engine import IncidentEngine

TUT = [{"name": "Padre Perez", "relation": "PADRE"}]
PICK = [{"name": "Tia Maria", "relation": "TIA", "phone": "7777-1111"},
        {"name": "Abuelo Jose", "relation": "ABUELO", "phone": "7777-2222"}]
EMG = [{"name": "Mama Lopez", "relation": "MADRE", "phone": "911"}]

def test_expediente_completo_validaciones(tmp_path) -> None:
    st = StudentRegistryEngine(
        SQLiteAdapter(tmp_path / "st.db"), FrozenClock())
    s = st.register(full_name="Ana Perez", level="BASICA",
        grade="3", birth_date="2016-05-10", sex="F",
        institution_id="INST-1", tutores=TUT,
        authorized_pickup=PICK, emergency_contacts=EMG,
        zid="ZID-TEST-1", zid_status="PROVISIONAL")
    assert s["zid_status"] == "PROVISIONAL"
    assert len(s["authorized_pickup"]) == 2
    assert len(s["tutores"]) == 1
    with pytest.raises(ValueError):
        st.register(full_name="X", level="BASICA",
            grade="1", tutores=[])
    with pytest.raises(ValueError):
        st.register(full_name="X", level="BASICA",
            grade="1", tutores=TUT, authorized_pickup=PICK[:1])
    assert "national_id" not in s
    assert "dui" not in s
    print("OK expediente: tutores+2 encargados+emergencia, sin datos de identidad")

def test_official_refs_fuente_y_verificacion(tmp_path) -> None:
    st = StudentRegistryEngine(
        SQLiteAdapter(tmp_path / "st2.db"), FrozenClock())
    s = st.register(full_name="Luis Gomez", level="BASICA",
        grade="1", tutores=TUT, authorized_pickup=PICK,
        emergency_contacts=EMG,
        official_refs=[{"ref_type": "PARTIDA",
            "value": "PN-123", "source": "PARENT",
            "status": "SELF_REPORTED"}])
    s2 = st.add_official_ref(s["student_id"],
        ref_type="NIE", value="NIE-999",
        source="SCHOOL", status="INSTITUTION_VERIFIED")
    assert len(s2["official_refs"]) == 2
    s3 = st.elevate_verification(s["student_id"],
        ref_type="NIE", new_status="MINED_VERIFIED")
    ref = [r for r in s3["official_refs"]
           if r["ref_type"] == "NIE"][0]
    assert ref["status"] == "MINED_VERIFIED"
    with pytest.raises(ValueError):
        st.elevate_verification(s["student_id"],
            ref_type="NIE", new_status="UNVERIFIED")
    print("OK official_refs: source/status + elevacion sin degradar")

def test_cupos_bloqueo_y_alternativas(tmp_path) -> None:
    cls = ClassroomEngine(
        SQLiteAdapter(tmp_path / "c.db"), FrozenClock())
    man = cls.create(name="1A-M", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="MATUTINA", capacity=2)
    tar = cls.create(name="1A-T", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="VESPERTINA", capacity=2)
    en = EnrollmentEngine(
        SQLiteAdapter(tmp_path / "e.db"), FrozenClock(),
        classroom_engine=cls)
    en.enroll(student_id="S1", classroom_id=man["classroom_id"],
        school_year="2026")
    en.enroll(student_id="S2", classroom_id=man["classroom_id"],
        school_year="2026")
    assert cls.get(man["classroom_id"])["status"] == "COMPLETADA"
    with pytest.raises(ValueError) as e:
        en.enroll(student_id="S3",
            classroom_id=man["classroom_id"],
            school_year="2026")
    assert "COMPLETADA" in str(e.value)
    alts = en.alternatives(institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1")
    assert len(alts) == 1
    assert alts[0]["turn"] == "VESPERTINA"
    r3 = en.enroll(student_id="S3",
        classroom_id=tar["classroom_id"],
        school_year="2026")
    assert r3["turn"] == "VESPERTINA"
    with pytest.raises(ValueError):
        en.enroll(student_id="S1",
            classroom_id=tar["classroom_id"],
            school_year="2026")
    en.withdraw(r3["enrollment_id"], "RETIRADA")
    assert cls.get(tar["classroom_id"])["cupos"] == 2
    print("OK cupos: llena->COMPLETADA + alternativas turno tarde + retiro libera")

def test_alertas_ausencia_y_notas(tmp_path) -> None:
    al = AlertEngine(SQLiteAdapter(tmp_path / "a.db"),
                     FrozenClock())
    at = __import__("apps.semilla.domain.attendance.attendance_engine",
        fromlist=["AttendanceEngine"]).AttendanceEngine(
        SQLiteAdapter(tmp_path / "at.db"), FrozenClock(),
        alert_engine=al)
    r = at.record(student_id="STU-A", date="2026-03-01",
        status="AUSENTE", recorded_by="TEA-1")
    assert r["parent_notified"] is True
    un = al.unread("STU-A")
    assert len(un) == 1
    assert un[0]["alert_type"] == "ABSENCE"
    ev = __import__("apps.semilla.domain.evaluation.evaluation_engine",
        fromlist=["EvaluationEngine"]).EvaluationEngine(
        SQLiteAdapter(tmp_path / "ev.db"), FrozenClock(),
        alert_engine=al)
    ev.register(student_id="STU-A", subject="Matematica",
        period="P1", score="8.50", teacher_id="TEA-1")
    un2 = al.unread("STU-A")
    assert len(un2) == 2
    assert un2[1]["alert_type"] == "GRADE_POSTED"
    al.mark_read(un[0]["alert_id"])
    assert len(al.unread("STU-A")) == 1
    print("OK alertas: ausencia + nueva nota + lectura")

def test_incidencias_avisan(tmp_path) -> None:
    al = AlertEngine(SQLiteAdapter(tmp_path / "a2.db"),
                     FrozenClock())
    inc = IncidentEngine(SQLiteAdapter(tmp_path / "i.db"),
        FrozenClock(), alert_engine=al)
    r = inc.report(student_id="STU-I",
        incident_type="HEALTH", severity="MEDIUM",
        detail="fiebre, se retira con encargada",
        reported_by="TEA-1")
    assert r["parent_notified"] is True
    assert len(al.unread("STU-I")) == 1
    inc.resolve(r["incident_id"], "retirada con madre")
    got = inc.incidents_of("STU-I")[0]
    assert got["resolved"] is True
    with pytest.raises(ValueError):
        inc.report(student_id="STU-I",
            incident_type="RARO", detail="x")
    print("OK incidencias: salud/conducta/permisos con aviso automatico")

def test_historial_verificable(tmp_path) -> None:
    h = __import__("apps.semilla.domain.academic.academic_history_engine",
        fromlist=["AcademicHistoryEngine"]).AcademicHistoryEngine(
        SQLiteAdapter(tmp_path / "h.db"), FrozenClock())
    h.append(student_id="STU-H", event_type="MATRICULA",
             detail="2026")
    h.append(student_id="STU-H", event_type="AVANCE",
             detail="1 a 2")
    assert h.verify() is True
    assert h.verify("STU-H") is True
    print("OK historial: hash-chain del ciclo escolar")
