import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.government.government_registry import GovernmentRegistry
from apps.nexo.domain.government.government_document_engine import GovernmentDocumentEngine
from apps.nexo.domain.government.government_coordination_engine import GovernmentCoordinationEngine
from apps.nexo.domain.government.government_audit_engine import GovernmentAuditEngine
from apps.nexo.domain.government.government_compliance_engine import GovernmentComplianceEngine
from apps.nexo.domain.government.government_reporting_engine import GovernmentReportingEngine
from apps.nexo.domain.government.government_validation_engine import GovernmentValidationEngine
from apps.nexo.application.government_use_cases.submit_government_document_use_case import SubmitGovernmentDocumentUseCase
from apps.nexo.application.government_use_cases.generate_government_report_use_case import GenerateGovernmentReportUseCase
from apps.nexo.application.government_use_cases.validate_regulatory_compliance_use_case import ValidateRegulatoryComplianceUseCase
from apps.nexo.application.government_use_cases.audit_government_process_use_case import AuditGovernmentProcessUseCase
from apps.nexo.application.government_use_cases.coordinate_institution_use_case import CoordinateInstitutionUseCase

def test_presupuesto_publico_ejecucion(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "gr.db")
    reg = GovernmentRegistry(db, FrozenClock())
    alc = reg.create_institution(
        name="Alcaldia de Soyapango",
        kind="MUNICIPALITY")
    prg = reg.create_program(
        institution_id=alc["institution_id"],
        name="Pavimentos 2026", period="2026",
        budgeted="100000.00")
    assert prg["committed"] == "0.00"
    p1 = reg.commit_funds(
        program_id=prg["program_id"],
        amount="40000")
    assert p1["committed"] == "40000.00"
    assert p1["available_budget"] == "60000.00"
    with pytest.raises(ValueError):
        reg.commit_funds(
            program_id=prg["program_id"],
            amount="70000")
    reg.accrue(program_id=prg["program_id"],
        amount="30000")
    with pytest.raises(ValueError):
        reg.accrue(program_id=prg["program_id"],
            amount="15000")
    p2 = reg.pay(program_id=prg["program_id"],
        amount="25000")
    assert p2["paid"] == "25000.00"
    assert p2["execution_pct"] == 25.0
    with pytest.raises(ValueError):
        reg.pay(program_id=prg["program_id"],
            amount="10000")
    print("OK presupuesto publico: 4 fases con validacion de saldos")

def test_documentos_verificacion(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "gd.db")
    docs = GovernmentDocumentEngine(db, FrozenClock())
    uc = SubmitGovernmentDocumentUseCase(docs)
    r = uc.execute(institution_id="GOV-1",
        doc_type="DECRETO",
        title="Decreto 2026-01",
        content="Contenido oficial del decreto")
    assert r["integrity_verified"] is True
    assert (r["document"]["content_hash"]
            != "")
    assert docs.verify_document(
        r["document"]["doc_id"],
        "contenido alterado") is False
    print("OK documentos: hash integridad + alteracion detectada")

def test_coordinacion_auditoria_cumplimiento(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "gc.db")
    clock = FrozenClock()
    coord = GovernmentCoordinationEngine(db, clock)
    uc = CoordinateInstitutionUseCase(coord)
    rq = uc.execute(
        from_institution="GOV-ALC",
        to_institution="GOV-MH",
        subject="Solicitud de transferencia",
        detail="Q1")
    assert rq["status"] == "SENT"
    coord.answer_request(request_id=rq["request_id"],
        response="Aprobada")
    inbox = coord.inbox_of("GOV-MH")
    assert inbox[0]["status"] == "ANSWERED"
    aud = GovernmentAuditEngine(db, clock)
    uca = AuditGovernmentProcessUseCase(aud)
    a = uca.execute(target_institution="GOV-ALC",
        process_ref="PRG-1", scope="compras",
        finding_severity="HIGH",
        finding_detail="falta soporte de 3 pagos")
    assert a["status"] == "OPEN"
    assert a["findings"][0]["severity"] == "HIGH"
    comp = GovernmentComplianceEngine(db, clock)
    ucv = ValidateRegulatoryComplianceUseCase(comp)
    rate = ucv.execute(institution_id="GOV-ALC",
        requirement="Ley de adquisiciones",
        compliant=True)
    assert rate["compliance_rate_pct"] == 100.0
    rate2 = ucv.execute(institution_id="GOV-ALC",
        requirement="Transparencia activa",
        compliant=False)
    assert rate2["compliance_rate_pct"] == 50.0
    assert rate2["violations"] == 1
    print("OK coordinacion+auditoria+cumplimiento (regla 57 informativo)")

def test_rendicion_cuentas(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "grpt.db")
    clock = FrozenClock()
    reg = GovernmentRegistry(db, clock)
    aud = GovernmentAuditEngine(db, clock)
    rep = GovernmentReportingEngine(db, clock,
        registry=reg, audit=aud)
    alc = reg.create_institution(
        name="Alcaldia", kind="MUNICIPALITY")
    reg.create_program(
        institution_id=alc["institution_id"],
        name="Programa A", period="2026-03",
        budgeted="50000")
    prg = reg.create_program(
        institution_id=alc["institution_id"],
        name="Programa B", period="2026-03",
        budgeted="50000")
    reg.commit_funds(program_id=prg["program_id"],
        amount="20000")
    reg.accrue(program_id=prg["program_id"],
        amount="15000")
    reg.pay(program_id=prg["program_id"],
        amount="10000")
    aud.start_audit(
        target_institution=alc["institution_id"],
        process_ref="x")
    r = GenerateGovernmentReportUseCase(rep).execute(
        institution_id=alc["institution_id"],
        period="2026-03")
    assert r["programs"] == 2
    assert r["budgeted"] == "100000.00"
    assert r["paid"] == "10000.00"
    assert r["execution_pct"] == 10.0
    assert r["open_audits"] == 1
    print("OK rendicion de cuentas: ejecucion + auditorias abiertas")

def test_validacion_gubernamental(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "gv.db")
    val = GovernmentValidationEngine(db, FrozenClock())
    r = val.validate_program(subject="PRG-X",
        budgeted="1000",
        institution_id="GOV-1", period="2026")
    assert r["valid"] is True
    r2 = val.validate_program(subject="PRG-Y",
        budgeted="0",
        institution_id="", period="")
    assert r2["valid"] is False
    print("OK validaciones gubernamentales: id unico por fila")
