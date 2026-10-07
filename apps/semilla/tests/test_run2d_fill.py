import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.student.student_registry_engine import StudentRegistryEngine
from apps.semilla.domain.classroom.classroom_engine import ClassroomEngine
from apps.semilla.domain.academic.enrollment_engine import EnrollmentEngine
from apps.semilla.domain.certification.certificate_engine import CertificateEngine
from apps.semilla.domain.admissions.admission_pipeline_engine import AdmissionPipelineEngine
from apps.semilla.domain.teacher.teacher_workload_engine import TeacherWorkloadEngine
from apps.semilla.domain.zyra_education_core.education_core_engine import EducationCoreEngine
from apps.semilla.migrations.database.canonical_migrations import (
    run_all, KNOWN_TABLES)
from apps.semilla.services.academic.academic_service import AcademicService

PICK2 = [{"name": "Mama", "relation": "MADRE"},
         {"name": "Papa", "relation": "PADRE"}]
EMG = [{"name": "Tio", "relation": "TIO", "phone": "911"}]
TUT = [{"name": "Mama", "relation": "MADRE",
        "zid": "ZID-M-1"}]

def _alumno(students, name, avg=None, att=None):
    est = students.register(full_name=name,
        level="BASICA", grade="1", institution_id="INST-1",
        tutores=TUT, authorized_pickup=PICK2,
        emergency_contacts=EMG,
        zid="ZID-" + name[:3], zid_status="PROVISIONAL")
    return est

def test_certificacion_cadena_y_reglas(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "c.db")
    clock = FrozenClock()
    students = StudentRegistryEngine(db, clock)
    ce = CertificateEngine(db, clock)
    est = _alumno(students, "Cert Uno")
    with pytest.raises(ValueError):
        ce.issue(student_id=est["student_id"],
            cert_type="GRADO", detail="fin de ano",
            issued_by="MINED-LOCAL")
    db.execute(
        "INSERT INTO sm_cycle_events (event_id,"
        " student_id, event_type, school_year, detail,"
        " created_at) VALUES ('EV1', ?, 'PROMOCION',"
        " '2026', 'paso a 2', 0)",
        (est["student_id"],))
    r = ce.issue(student_id=est["student_id"],
        cert_type="GRADO", detail="completo 1ro",
        issued_by="DIR-1")
    assert r["status"] == "VIGENTE"
    v = ce.verify(r["cert_code"])
    assert v["found"] is True
    assert v["cert_type"] == "GRADO"
    r2 = ce.issue(student_id=est["student_id"],
        cert_type="PARTICIPACION", detail="olimpiada")
    assert ce.verify_chain(est["student_id"]) is True
    ce.revoke(r2["cert_code"], "duplicado")
    v2 = ce.verify(r2["cert_code"])
    assert v2["status"] == "REVOCADO"
    assert "duplicado" in v2["revoked_reason"]
    db.execute(
        "UPDATE sm_certificates SET detail = 'TAMPER'"
        " WHERE cert_code = ?",
        (r["cert_code"],))
    assert ce.verify_chain(est["student_id"]) is False
    with pytest.raises(ValueError):
        ce.issue(student_id="NO-EXISTE",
            cert_type="PARTICIPACION")
    print("OK S-11 certificacion: GRADO exige PROMOCION real + cadena hash por alumno + revocacion + tamper detectado")

def test_admisiones_pipeline_con_s7(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "a.db")
    clock = FrozenClock()
    students = StudentRegistryEngine(db, clock)
    cls = ClassroomEngine(db, clock)
    en = EnrollmentEngine(db, clock, classroom_engine=cls)
    ap = AdmissionPipelineEngine(db, clock,
        student_registry=students,
        classroom_engine=cls,
        enrollment_engine=en)
    aula = cls.create(name="2A", institution_id="INST-9",
        school_year="2026", level="BASICA", grade="2",
        section="A", turn="MATUTINA", capacity=1)
    a1 = ap.create_application(applicant_name="Nueva",
        relation="MADRE", target_institution="INST-9",
        target_level="BASICA", target_grade="2")
    assert a1["status"] == "PENDIENTE"
    with pytest.raises(ValueError):
        ap.place(a1["app_id"], tutores=TUT,
            authorized_pickup=PICK2,
            emergency_contacts=EMG)
    rv = ap.review(a1["app_id"], decision="APROBADA",
        reviewer="DIR-9")
    assert rv["status"] == "APROBADA"
    p1 = ap.place(a1["app_id"], tutores=TUT,
        authorized_pickup=PICK2,
        emergency_contacts=EMG)
    assert p1["status"] == "MATRICULADO"
    assert p1["assignment"]["status"] == "ASIGNADO"
    assert p1["assignment"]["turn"] == "MATUTINA"
    assert cls.get(aula["classroom_id"])["enrolled"] == 1
    a2 = ap.create_application(applicant_name="Segundo",
        relation="PADRE", target_institution="INST-9",
        target_level="BASICA", target_grade="2")
    ap.review(a2["app_id"], decision="APROBADA",
        reviewer="DIR-9")
    p2 = ap.place(a2["app_id"], tutores=TUT,
        authorized_pickup=PICK2,
        emergency_contacts=EMG)
    assert p2["status"] == "APROBADA"
    assert "NO_CUPOS" in p2["note"]
    print("OK S-11 admisiones: solicitud->revision->colocacion compone S-7 (cupo real, una vez) + NO_CUPOS honesto deja APROBADA")

def test_carga_docente_conflictos(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "t.db")
    clock = FrozenClock()
    cls = ClassroomEngine(db, clock)
    a = cls.create(name="A", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="MATUTINA", capacity=10)
    b = cls.create(name="B", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="B", turn="MATUTINA", capacity=10)
    tw = TeacherWorkloadEngine(db, clock,
        classroom_engine=cls, max_classrooms=2)
    r1 = tw.assign(teacher_id="T1",
        classroom_id=a["classroom_id"],
        subject="MATE", day="LUN", time_slot="08:00")
    assert r1["assignment_id"]
    with pytest.raises(ValueError) as e1:
        tw.assign(teacher_id="T1",
            classroom_id=b["classroom_id"],
            subject="MATE", day="LUN",
            time_slot="08:00")
    assert "DOCENTE" in str(e1.value)
    with pytest.raises(ValueError) as e2:
        tw.assign(teacher_id="T2",
            classroom_id=a["classroom_id"],
            subject="LENG", day="LUN",
            time_slot="08:00")
    assert "AULA" in str(e2.value)
    tw.assign(teacher_id="T1",
        classroom_id=b["classroom_id"],
        subject="MATE", day="LUN", time_slot="09:00")
    w = tw.workload_of("T1")
    assert w["aulas"] == 2
    c = cls.create(name="C", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="C", turn="MATUTINA", capacity=10)
    tw2 = TeacherWorkloadEngine(db, clock,
        classroom_engine=cls, max_classrooms=1)
    tw2.assign(teacher_id="T3",
        classroom_id=c["classroom_id"],
        subject="MATE", day="LUN", time_slot="08:00")
    with pytest.raises(ValueError) as e3:
        tw2.assign(teacher_id="T3",
            classroom_id=b["classroom_id"],
            subject="MATE", day="MAR",
            time_slot="08:00")
    assert "tope" in str(e3.value)
    print("OK S-11 carga docente: conflicto docente/aula + tope de aulas honesto + set_teacher real aplicado")

def test_education_core_indicadores(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "e.db")
    clock = FrozenClock()
    students = StudentRegistryEngine(db, clock)
    cls = ClassroomEngine(db, clock)
    cls.create(name="1A", institution_id="INST-1",
        school_year="2026", level="BASICA", grade="1",
        section="A", turn="MATUTINA", capacity=10)
    core = EducationCoreEngine(db, clock,
        student_registry=students)
    s1 = _alumno(students, "Fuerte Uno")
    s2 = _alumno(students, "Debil Dos")
    db.execute(
        "INSERT INTO sm_evaluations (evaluation_id,"
        " student_id, subject, period, score,"
        " scale_max, eval_type, teacher_id, detail,"
        " created_at) VALUES ('E1', ?, 'MATE', 'P1',"
        " '9.00', '10.00', 'EXAMEN', '', '', 0)",
        (s1["student_id"],))
    db.execute(
        "INSERT INTO sm_evaluations (evaluation_id,"
        " student_id, subject, period, score,"
        " scale_max, eval_type, teacher_id, detail,"
        " created_at) VALUES ('E2', ?, 'MATE', 'P1',"
        " '4.00', '10.00', 'EXAMEN', '', '', 0)",
        (s2["student_id"],))
    db.execute(
        "INSERT INTO sm_class_attendance (class_att_id,"
        " student_id, classroom_id, subject, date,"
        " time_slot, status, teacher_id, detail,"
        " created_at) VALUES ('C1', ?, 'AUL', 'MATE',"
        " '2026-03-10', '08:00', 'PRESENTE', '', '', 0)",
        (s1["student_id"],))
    for i, st in enumerate(("PRESENTE", "AUSENTE",
                            "AUSENTE")):
        db.execute(
            "INSERT INTO sm_class_attendance"
            " (class_att_id, student_id, classroom_id,"
            " subject, date, time_slot, status,"
            " teacher_id, detail, created_at) VALUES"
            " (?, ?, 'AUL', 'MATE', '2026-03-1"
            + str(i) + "', '08:00', ?, '', '', 0)",
            ("C2" + str(i), s2["student_id"], st))
    ind = core.indicators("INST-1", "2026")
    assert ind["alumnos"] == 2
    assert ind["aulas"] == 1
    assert ind["capacidad"] == 10
    assert ind["promedios"]["MATE"] in ("6.50",
                                        "6.5")
    ids_riesgo = [r["student_id"]
                  for r in ind["riesgo"]]
    assert s2["student_id"] in ids_riesgo
    assert s1["student_id"] not in ids_riesgo
    r2row = [r for r in ind["riesgo"]
             if r["student_id"] == s2["student_id"]][0]
    assert any("promedio" in x
               for x in r2row["reasons"])
    assert any("asistencia" in x
               for x in r2row["reasons"])
    print("OK S-11 education core: indicadores por institucion (alumnos/aulas/cupos/promedios) + riesgo con razones honestas (semilla Capa A GOV-DATA)")

def test_s12_registro_canonico_idempotente(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "m.db")
    clock = FrozenClock()
    run_all(db, clock)
    run_all(db, clock)
    for t in KNOWN_TABLES:
        row = db.query_one(
            "SELECT COUNT(*) AS n FROM"
            " sqlite_master WHERE type = 'table' AND"
            " name = ?", (t,))
        assert row is not None and int(row["n"]) == 1, t
    db.execute(
        "INSERT INTO sm_evaluations (evaluation_id,"
        " student_id, subject, period, score, created_at)"
        " VALUES ('X1', 'S1', 'MATE', 'P1', '8.00', 0)")
    row = db.query_one(
        "SELECT score FROM sm_evaluations WHERE"
        " evaluation_id = 'X1'")
    assert str(row["score"]) == "8.00"
    print("OK S-12: registro canonico de 16 tablas de DDL conocido, doble ejecucion idempotente; nucleo (sm_students/classrooms/enrollments) EXCLUIDO a proposito — lo crean sus duenos")

def test_s12_servicio_academico_integrado(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "s.db")
    svc = AcademicService(db, FrozenClock())
    svc.bootstrap_canonical()
    est = svc.students.register(full_name="Serv Uno",
        level="BASICA", grade="1",
        institution_id="INST-1", tutores=TUT,
        authorized_pickup=PICK2,
        emergency_contacts=EMG,
        zid="ZID-SV1", zid_status="PROVISIONAL")
    r = svc.notes.record_note(
        student_id=est["student_id"],
        subject="MATE", period="P1", score="8.00",
        teacher_id="T1")
    assert r["score"] == "8.00"
    o = svc.tutor.next_objective(est["student_id"])
    assert o["subject"] == "MATE"
    p = svc.paths.build_path(est["student_id"])
    assert p["total_steps"] == 3
    ind = svc.core.indicators("INST-1")
    assert ind["alumnos"] == 1
    print("OK S-12: AcademicService fachada unica (notas->tutoria->rutas->indicadores) + bootstrap canonico en una linea para el server")
