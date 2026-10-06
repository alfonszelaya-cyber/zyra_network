import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.student.talent_engine import TalentEngine
from apps.semilla.domain.scholarship.scholarship_engine import ScholarshipEngine
from apps.semilla.domain.finance.school_payments_gateway import SchoolPaymentsGateway
from apps.semilla.domain.finance.education_economy_engine import EducationEconomyEngine
from apps.semilla.domain.evaluation.evaluation_engine import EvaluationEngine
from apps.semilla.domain.attendance.attendance_engine import AttendanceEngine
from apps.semilla.domain.notifications.alert_engine import AlertEngine
from apps.semilla.application.student_use_cases.detect_talent_use_case import DetectTalentUseCase
from apps.semilla.application.scholarship_use_cases.apply_scholarship_use_case import ApplyScholarshipUseCase

def test_talento_registro_mentoria_aceleracion(tmp_path) -> None:
    al = AlertEngine(SQLiteAdapter(tmp_path / "a.db"),
                     FrozenClock())
    t = TalentEngine(SQLiteAdapter(tmp_path / "t.db"),
                     FrozenClock(), alert_engine=al)
    tal = t.register_talent(student_id="STU-1",
        category="MATEMATICAS", detail="promedio 9.8",
        source="TUTOR", score="9.8")
    assert tal["status"] == "DETECTED"
    assert len(al.unread("STU-1")) == 1
    m = t.assign_mentor(talent_id=tal["talent_id"],
        mentor_name="Ing. Rivas", mentor_ref="MIT-CLUB")
    assert m["status"] == "MENTORED"
    ac = t.accelerate(talent_id=tal["talent_id"],
        detail="paso a olimpiada nacional")
    assert ac["status"] == "ACCELERATED"
    assert len(t.national_registry()) == 1
    with pytest.raises(ValueError):
        t.register_talent(student_id="STU-1",
                          category="", detail="x")
    print("OK talento: detectar->mentor->acelerar + alerta + registro nacional")

def test_usecase_detecta_talentos_por_promedio(tmp_path) -> None:
    ev = EvaluationEngine(
        SQLiteAdapter(tmp_path / "ev.db"), FrozenClock())
    t = TalentEngine(SQLiteAdapter(tmp_path / "t2.db"),
                     FrozenClock())
    ev.register(student_id="STU-2", subject="Matematica",
        period="P1", score="9.8")
    ev.register(student_id="STU-2", subject="Fisica",
        period="P1", score="9.2")
    ev.register(student_id="STU-2", subject="Lenguaje",
        period="P1", score="6.0")
    uc = DetectTalentUseCase(ev, t, min_average="9.00")
    r = uc.execute(student_id="STU-2")
    assert r["talents_registered"] == 2
    cats = [x["category"] for x in r["talents"]]
    assert "Matematica" in cats and "Fisica" in cats
    assert "Lenguaje" not in cats
    print("OK use case talento: execute existe y detecta por umbral 9.0")

def test_beca_flujo_completo(tmp_path) -> None:
    ev = EvaluationEngine(
        SQLiteAdapter(tmp_path / "ev.db"), FrozenClock())
    at = AttendanceEngine(
        SQLiteAdapter(tmp_path / "at.db"), FrozenClock())
    sch = ScholarshipEngine(
        SQLiteAdapter(tmp_path / "s.db"), FrozenClock(),
        evaluation_engine=ev, attendance_engine=at)
    for subj in ("Matematica", "Lenguaje", "Ciencias"):
        ev.register(student_id="STU-G", subject=subj,
            period="P1", score="9.0")
    at.record(student_id="STU-G", date="2026-03-01",
        status="PRESENTE")
    prg = sch.create_program(name="Beca Excelencia",
        funder="Fondo ZYRA", min_average="8.00",
        min_attendance_pct=85.0, slots=1)
    uc = ApplyScholarshipUseCase(sch)
    r = uc.execute(program_id=prg["program_id"],
        student_id="STU-G")
    assert r["application"]["status"] == "APPROVED"
    d = sch.disburse(
        application_id=r["application"]["application_id"],
        amount="500.00", method="transferencia")
    assert d["status"] == "DISBURSED"
    assert d["disbursed_amount"] == "500.00"
    print("OK beca: aplicar->evaluar->APPROVED->desembolsar")

def test_beca_rechazos_por_criterios_y_slots(tmp_path) -> None:
    ev = EvaluationEngine(
        SQLiteAdapter(tmp_path / "ev2.db"), FrozenClock())
    at = AttendanceEngine(
        SQLiteAdapter(tmp_path / "at2.db"), FrozenClock())
    sch = ScholarshipEngine(
        SQLiteAdapter(tmp_path / "s2.db"), FrozenClock(),
        evaluation_engine=ev, attendance_engine=at)
    prg = sch.create_program(name="Beca Unica",
        min_average="8.00", min_attendance_pct=85.0,
        slots=1)
    ev.register(student_id="STU-MAL", subject="X",
        period="P1", score="6.0")
    ev.register(student_id="STU-BN", subject="X",
        period="P1", score="9.0")
    ev.register(student_id="STU-B2", subject="X",
        period="P1", score="9.0")
    at.record(student_id="STU-BN", date="2026-03-01",
        status="PRESENTE")
    at.record(student_id="STU-B2", date="2026-03-01",
        status="PRESENTE")
    a1 = sch.apply(program_id=prg["program_id"],
        student_id="STU-MAL")
    r1 = sch.evaluate(a1["application_id"])
    assert r1["status"] == "REJECTED"
    assert "criterios" in r1["reason"]
    a2 = sch.apply(program_id=prg["program_id"],
        student_id="STU-BN")
    r2 = sch.evaluate(a2["application_id"])
    assert r2["status"] == "APPROVED"
    a3 = sch.apply(program_id=prg["program_id"],
        student_id="STU-B2")
    r3 = sch.evaluate(a3["application_id"])
    assert r3["status"] == "REJECTED"
    assert "slots" in r3["reason"]
    with pytest.raises(ValueError):
        sch.apply(program_id=prg["program_id"],
            student_id="STU-BN")
    print("OK beca rechazos: no cumple criterios + sin slots + duplicado")

def test_pagos_escolares_honesto_y_real(tmp_path) -> None:
    gw = SchoolPaymentsGateway(
        SQLiteAdapter(tmp_path / "p1.db"), FrozenClock())
    assert gw.mode == "not_configured"
    r = gw.pay(payer_zid="ZID-P", payee_zid="ZID-ESC",
        student_id="STU-P", fee_type="MATRICULA",
        amount="50.00")
    assert r["status"] == "not_configured"
    class FakePaymentsEngine:
        def send_money(self, *, payer_zid, payee_zid,
                       amount, currency, instrument_id,
                       note=""):
            return {"sent": True, "ref": "NET-123"}
    gw2 = SchoolPaymentsGateway(
        SQLiteAdapter(tmp_path / "p2.db"), FrozenClock(),
        payments_engine=FakePaymentsEngine())
    assert gw2.mode == "red_payments"
    r2 = gw2.pay(payer_zid="ZID-P", payee_zid="ZID-ESC",
        student_id="STU-P", fee_type="MENSUALIDAD",
        amount="125.00", instrument_id="CARD-1",
        reference="MARZO")
    assert r2["status"] == "REGISTERED"
    assert r2["network"]["sent"] is True
    with pytest.raises(ValueError):
        gw2.pay(payer_zid="Z", payee_zid="Z",
            student_id="STU-P", fee_type="INVALIDO",
            amount="10")
    assert gw2.total_paid("STU-P") == "125.00"
    print("OK pagos escolares: SE-4 via Red + honesto + total Decimal")

def test_economia_subsidios_bonos_trazabilidad(tmp_path) -> None:
    eco = EducationEconomyEngine(
        SQLiteAdapter(tmp_path / "ec.db"), FrozenClock())
    eco.assign_subsidy(student_id="STU-EC",
        subsidy_type="TRANSPORTE", amount="40.00",
        reason="zona rural", approved_by="DIR-1")
    eco.assign_bonus(student_id="STU-EC",
        bonus_type="MERITO", amount="25.00",
        reason="mejor promedio", approved_by="DIR-1")
    tr = eco.trace("STU-EC")
    assert len(tr) == 2
    assert eco.total_aid("STU-EC") == "65.00"
    with pytest.raises(ValueError):
        eco.assign_subsidy(student_id="STU-EC",
            subsidy_type="X", amount="-5")
    print("OK economia educativa: subsidio+bono+trazabilidad Decimal")
