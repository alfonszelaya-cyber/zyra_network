import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.semilla.domain.security.idempotency_engine import IdempotencyEngine
from apps.semilla.domain.security.rbac_engine import RbacEngine
from apps.semilla.domain.security.access_audit_engine import AccessAuditEngine
from apps.semilla.domain.security.child_data_protection_engine import ChildDataProtectionEngine
from apps.semilla.domain.family.family_engine import FamilyEngine

def test_idempotencia_claim_complete_replay(tmp_path) -> None:
    eng = IdempotencyEngine(
        SQLiteAdapter(tmp_path / "idem.db"), FrozenClock())
    c1 = eng.claim(key="cert-1", scope="certificacion")
    assert c1["first"] is True
    eng.complete(key="cert-1", scope="certificacion",
                 result={"credential": "CRD-1"})
    c2 = eng.claim(key="cert-1", scope="certificacion")
    assert c2["first"] is False
    assert c2["result"] == {"credential": "CRD-1"}
    assert eng.claim(key="cert-2",
                     scope="certificacion")["first"] is True
    eng.forget(key="cert-1", scope="certificacion")
    assert eng.claim(key="cert-1",
                     scope="certificacion")["first"] is True
    print("OK idempotencia: claim/complete/replay/forget")

def test_rbac_6_roles_permisos(tmp_path) -> None:
    rb = RbacEngine(SQLiteAdapter(tmp_path / "rb.db"),
                    FrozenClock())
    rb.assign(actor="maestro1", role="TEACHER",
              institution_id="INST-1")
    rb.assign(actor="papa1", role="PARENT",
              student_scope="STU-1")
    rb.assign(actor="director1", role="DIRECTOR",
              institution_id="INST-1")
    rb.assign(actor="ministro", role="GOVERNMENT")
    rb.assign(actor="alumno1", role="STUDENT")
    r1 = rb.can(actor="maestro1", action="WRITE_GRADES")
    assert r1["allowed"] is True
    r2 = rb.can(actor="papa1", action="WRITE_GRADES")
    assert r2["allowed"] is False
    r3 = rb.can(actor="papa1", action="GRANT_CONSENT")
    assert r3["allowed"] is True
    r4 = rb.can(actor="alumno1", action="WRITE_GRADES")
    assert r4["allowed"] is False
    r5 = rb.can(actor="ministro", action="VIEW_NATIONAL")
    assert r5["allowed"] is True
    r6 = rb.can(actor="nadie", action="READ_STUDENT")
    assert r6["allowed"] is False
    with pytest.raises(ValueError):
        rb.assign(actor="x", role="HACKER")
    print("OK RBAC: 6 roles, maestro escribe notas, padre consiente, gobierno ve nacional, sin rol denegado")

def test_proteccion_menores_consentimiento_fail_closed(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "cp.db")
    clock = FrozenClock()
    rb = RbacEngine(db, clock)
    fa = FamilyEngine(db, clock)
    au = AccessAuditEngine(db, clock)
    cp = ChildDataProtectionEngine(rbac_engine=rb,
        family_engine=fa, audit_engine=au)
    rb.assign(actor="TEA-1", role="TEACHER")
    rb.assign(actor="DIR-1", role="DIRECTOR")
    r1 = cp.request_sensitive(actor="TEA-1",
        student_id="STU-M", action="EXPORT_FULL_RECORD")
    assert r1["allowed"] is False
    assert "consentimiento" in r1["reason"]
    fa.grant_consent(student_id="STU-M",
        consent_type="DATA_PROCESSING",
        granted_by="PADRE")
    r2 = cp.request_sensitive(actor="TEA-1",
        student_id="STU-M", action="EXPORT_FULL_RECORD")
    assert r2["allowed"] is True
    r3 = cp.request_sensitive(actor="DIR-1",
        student_id="STU-M", action="SHARE_EXTERNAL",
        consent_type="PHOTOS")
    assert r3["allowed"] is False
    hist = au.history_of("STU-M")
    assert len(hist) == 3
    assert all("allowed" in h for h in hist)
    print("OK proteccion menores: fail-closed sin consentimiento + permitido con consentimiento + 3 accesos auditados")

def test_minimizacion_por_rol(tmp_path) -> None:
    db = SQLiteAdapter(tmp_path / "mm.db")
    clock = FrozenClock()
    rb = RbacEngine(db, clock)
    fa = FamilyEngine(db, clock)
    au = AccessAuditEngine(db, clock)
    cp = ChildDataProtectionEngine(rbac_engine=rb,
        family_engine=fa, audit_engine=au)
    rb.assign(actor="TEA-1", role="TEACHER")
    rb.assign(actor="PAP-1", role="PARENT")
    rb.assign(actor="EMP-1", role="COMPANY")
    profile = {"full_name": "Ana", "level": "BASICA",
        "grade": "3", "average": "8.50",
        "attendance_pct": "95.00",
        "tutores": [{"name": "Padre"}],
        "emergency_contacts": [{"phone": "911"}]}
    v1 = cp.filtered_profile(actor="TEA-1",
        student_id="STU-1", profile=profile)
    assert v1["allowed"] is True
    assert "full_name" in v1
    assert "tutores" not in v1
    assert "emergency_contacts" not in v1
    v2 = cp.filtered_profile(actor="PAP-1",
        student_id="STU-1", profile=profile)
    assert v2["allowed"] is False
    v3 = cp.filtered_profile(actor="EMP-1",
        student_id="STU-1", profile=profile)
    assert v3["allowed"] is False
    print("OK minimizacion: teacher ve academicos, parent/company denegados (solo su hijo via scope)")

def test_regresion_imports_semilla() -> None:
    import importlib, pathlib
    BASE = (pathlib.Path(__file__).resolve().parents[1]
            / "domain" / "security")
    n = 0
    for p in sorted(BASE.glob("*.py")):
        if p.stat().st_size <= 1:
            continue
        importlib.import_module(
            "apps.semilla.domain.security." + p.stem)
        n = n + 1
    assert n >= 4
    print("OK seguridad: " + str(n) + " modulos importan")
