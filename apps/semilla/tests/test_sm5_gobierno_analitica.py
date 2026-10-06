import pytest
from decimal import Decimal as _D
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.institution.institution_registry_engine import InstitutionRegistryEngine
from apps.semilla.domain.institution.institution_verification_engine import InstitutionVerificationEngine
from apps.semilla.domain.government.governance_engine import GovernanceEngine
from apps.semilla.domain.analytics.analytics_engine import AnalyticsEngine
from apps.semilla.domain.reports.report_engine import SemillaReportEngine
from apps.semilla.domain.student.student_registry_engine import StudentRegistryEngine
from apps.semilla.domain.academic.enrollment_engine import EnrollmentEngine
from apps.semilla.domain.classroom.classroom_engine import ClassroomEngine
from apps.semilla.domain.evaluation.evaluation_engine import EvaluationEngine

def test_verificacion_institucion_elevable(tmp_path) -> None:
    ve = InstitutionVerificationEngine(
        SQLiteAdapter(tmp_path / "v.db"), FrozenClock())
    d = ve.submit_document(institution_id="INST-1",
        document_ref="RESOLUCION-MINED-2026-001")
    assert d["status"] == "PENDING"
    e1 = ve.elevate(d["verify_id"],
        new_status="INSTITUTION_VERIFIED",
        verified_by="DIRECTOR-1")
    assert e1["status"] == "INSTITUTION_VERIFIED"
    e2 = ve.elevate(d["verify_id"],
        new_status="MINED_VERIFIED",
        verified_by="MINED-DEPTO")
    assert e2["status"] == "MINED_VERIFIED"
    with pytest.raises(ValueError):
        ve.elevate(d["verify_id"],
            new_status="PENDING", verified_by="x")
    print("OK verificacion institucion: elevable sin degradar")

def test_gobernanza_supervision_politicas(tmp_path) -> None:
    go = GovernanceEngine(
        SQLiteAdapter(tmp_path / "g.db"), FrozenClock())
    sup = go.supervise(institution_id="INST-1",
        supervisor="Supervisor Zona 3",
        findings="documentacion en orden")
    assert sup["status"] == "OPEN"
    c = go.close_supervision(sup["supervision_id"])
    assert c["status"] == "CLOSED"
    p = go.create_policy(title="Uso de IA en aulas",
        scope="NATIONAL", detail="reglas de uso")
    a = go.activate_policy(p["policy_id"])
    assert a["status"] == "ACTIVE"
    with pytest.raises(ValueError):
        go.supervise(institution_id="INST-2",
                     supervisor="")
    print("OK gobernanza: supervision + politicas")

def test_dashboard_ministerial(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "md.db")
    clock = FrozenClock()
    ireg = InstitutionRegistryEngine(db, clock)
    inst = ireg.register(name="Escuela Central",
        levels=["BASICA"])
    st = StudentRegistryEngine(db, clock)
    TUT = [{"name": "Padre", "relation": "PADRE"}]
    PICK = [{"name": "Tia", "relation": "TIA"},
            {"name": "Abuelo", "relation": "ABUELO"}]
    EMG = [{"name": "Mama", "relation": "MADRE"}]
    for i in range(3):
        st.register(full_name="Alumno " + str(i),
            level="BASICA", grade=str(i + 1),
            institution_id=inst["institution_id"],
            tutores=TUT, authorized_pickup=PICK,
            emergency_contacts=EMG)
    cls = ClassroomEngine(db, clock)
    room = cls.create(name="Aula 1",
        institution_id=inst["institution_id"],
        school_year="2026", level="BASICA", grade="1",
        capacity=30)
    en = EnrollmentEngine(db, clock, classroom_engine=cls)
    s1 = st.by_institution(inst["institution_id"])[0]
    en.enroll(student_id=s1["student_id"],
        classroom_id=room["classroom_id"],
        school_year="2026")
    go = GovernanceEngine(db, clock)
    dash = go.ministry_dashboard(registry=ireg,
        enrollment_engine=en)
    assert dash["institutions"] == 1
    assert dash["enrolled_2026"] == 1
    print("OK dashboard ministerial: roster real")

def test_analitica_estudiante_escuela_nacion(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "an.db")
    clock = FrozenClock()
    ev = EvaluationEngine(db, clock)
    ireg = InstitutionRegistryEngine(db, clock)
    reg = StudentRegistryEngine(db, clock)
    inst1 = ireg.register(name="Escuela A")
    TUT = [{"name": "Padre", "relation": "PADRE"}]
    PICK = [{"name": "Tia", "relation": "TIA"},
            {"name": "Abuelo", "relation": "ABUELO"}]
    EMG = [{"name": "Mama", "relation": "MADRE"}]
    ids1 = []
    for i in range(2):
        s = reg.register(full_name="A" + str(i),
            level="BASICA", grade="1",
            institution_id=inst1["institution_id"],
            tutores=TUT, authorized_pickup=PICK,
            emergency_contacts=EMG)
        ids1.append(s["student_id"])
    ev.register(student_id=ids1[0], subject="Matematica",
        period="P1", score="9.0")
    ev.register(student_id=ids1[0], subject="Lenguaje",
        period="P1", score="8.0")
    ev.register(student_id=ids1[1], subject="Matematica",
        period="P1", score="7.0")
    an = AnalyticsEngine(db, clock, evaluation_engine=ev,
        student_registry=reg)
    sr = an.student_report(ids1[0])
    assert sr["average"] == "8.50"
    assert sr["best_subject"] == "Matematica"
    assert sr["weak_subject"] == "Lenguaje"
    sch = an.school_report(ids1, inst1["institution_id"])
    assert sch["students"] == 2
    esperado = str(((_D("8.50") + _D("7.00"))
                    / _D("2")).quantize(_D("0.01")))
    assert esperado == "7.75"
    assert sch["school_average"] == esperado
    nat = an.national_report([inst1["institution_id"]],
        reg)
    assert nat["institutions"] == 1
    assert nat["national_average"] == "7.75"
    print("OK analitica: estudiante 8.50 + escuela 7.75 (promedio de promedios, calculado en el test) + nacional")
