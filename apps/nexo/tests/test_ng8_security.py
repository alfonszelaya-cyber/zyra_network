import pytest
from shared_engines.common.clocks import FrozenClock
from shared_engines.storage.database import SQLiteAdapter
from apps.nexo.domain.security_identity.identity_engine import NexoIdentityRefEngine
from apps.nexo.domain.security_identity.authentication_engine import NexoAuthenticationEngine
from apps.nexo.domain.security_identity.authorization_engine import NexoAuthorizationEngine
from apps.nexo.domain.security_identity.access_control_engine import NexoAccessControlEngine
from apps.nexo.domain.security_identity.biometric_engine import NexoBiometricAdapter
from apps.nexo.domain.security_identity.security_monitor_engine import NexoSecurityMonitor
from apps.nexo.domain.security_identity.identity_audit_engine import NexoIdentityAudit
from apps.nexo.domain.identity.identity_registry import NexoIdentityRegistry
from apps.nexo.domain.identity.credential_manager import NexoCredentialManager
from apps.nexo.domain.identity.identity_validation import NexoIdentityValidation
from apps.nexo.application.identity_use_cases.register_identity_use_case import RegisterIdentityUseCase
from apps.nexo.application.identity_use_cases.validate_identity_record_use_case import ValidateIdentityRecordUseCase
from apps.nexo.application.identity_use_cases.manage_credentials_use_case import ManageCredentialsUseCase

def _db(tmp_path, name):
    return SQLiteAdapter(tmp_path / name), FrozenClock()

def test_identity_refs_regla63(tmp_path) -> None:
    db, clock = _db(tmp_path, "ir.db")
    eng = NexoIdentityRefEngine(db, clock)
    ref = eng.register_reference(zid="ZID-TEST-001",
        provider="RNPN",
        provider_reference="REF-ABC-123",
        assurance_level="L5", evidence_hash="abc123")
    assert ref["provider"] == "RNPN"
    keys = set(ref.keys())
    assert "national_id" not in keys
    assert "dui" not in keys
    assert "birth_date" not in keys
    assert eng.is_current(ref["ref_id"]) is True
    exp = eng.register_reference(zid="ZID-TEST-002",
        provider="PASSPORT",
        provider_reference="P-1",
        expires_at=clock.now() - 100)
    assert eng.is_current(exp["ref_id"]) is False
    eng.suspend(ref["ref_id"])
    assert eng.is_current(ref["ref_id"]) is False
    assert len(eng.refs_of("ZID-TEST-001")) == 1
    print("OK identidad: solo referencias (regla 63) + frescura")

def test_rbac_montos(tmp_path) -> None:
    db, clock = _db(tmp_path, "az.db")
    az = NexoAuthorizationEngine(db, clock)
    az.grant(company_id="EMP-1", actor="cajero",
        role="OPERATOR", max_amount="1000")
    az.grant(company_id="EMP-1", actor="gerente",
        role="APPROVER", max_amount="50000")
    r1 = az.can(actor="cajero", company_id="EMP-1",
        role_needed="OPERATOR", amount="500")
    assert r1["allowed"] is True
    r2 = az.can(actor="cajero", company_id="EMP-1",
        role_needed="OPERATOR", amount="2000")
    assert r2["allowed"] is False
    assert "excede" in r2["reason"]
    r3 = az.can(actor="cajero", company_id="EMP-1",
        role_needed="APPROVER", amount="10")
    assert r3["allowed"] is False
    r4 = az.can(actor="nadie", company_id="EMP-1",
        role_needed="VIEWER")
    assert r4["allowed"] is False
    ac = NexoAccessControlEngine(az)
    d1 = ac.decide(actor="gerente",
        company_id="EMP-1", action="APPROVE",
        amount="10000")
    assert d1["allowed"] is True
    d2 = ac.decide(actor="cajero",
        company_id="EMP-1", action="APPROVE",
        amount="10")
    assert d2["allowed"] is False
    d3 = ac.decide(actor="x", company_id="EMP-1",
        action="EXPLOTAR")
    assert d3["allowed"] is False
    print("OK RBAC: roles jerarquicos + tope monto + decisiones")

def test_sessions_monitor_audit(tmp_path) -> None:
    db, clock = _db(tmp_path, "sm.db")
    auth = NexoAuthenticationEngine(db, clock)
    s = auth.open_session(zid="ZID-TEST-001",
        ttl_seconds=3600)
    assert auth.active_session(
        "ZID-TEST-001") is not None
    auth.end_session(s["session_id"])
    assert auth.active_session(
        "ZID-TEST-001") is None
    mon = NexoSecurityMonitor(db, clock)
    mon.log_event(event_type="LOGIN_FAILED",
        actor="intruso", severity="HIGH",
        detail="3 intentos")
    mon.log_event(event_type="LOGIN_OK",
        actor="cajero")
    assert (mon.counts_by_type().get(
        "LOGIN_FAILED") == 1)
    aud = NexoIdentityAudit(db, clock)
    aud.record(zid="ZID-TEST-001",
        action="REGISTER_REFERENCE",
        actor="admin")
    aud.record(zid="ZID-TEST-001",
        action="CRED_ISSUED", actor="admin")
    h = aud.history_of("ZID-TEST-001")
    assert len(h) == 2
    bio = NexoBiometricAdapter()
    r = bio.verify(zid="ZID-1", reference="x")
    assert r["verified"] is False
    assert r["fail_closed"] is True
    print("OK sesiones+monitor+auditoria+biometria fail-closed")

def test_identity_usecases(tmp_path) -> None:
    db, clock = _db(tmp_path, "iu.db")
    val = NexoIdentityValidation(db, clock)
    reg = NexoIdentityRegistry(db, clock)
    refs = NexoIdentityRefEngine(db, clock)
    aud = NexoIdentityAudit(db, clock)
    uc = RegisterIdentityUseCase(val, reg, refs, aud)
    r = uc.execute(zid="ZID-TEST-100",
        provider="RNPN",
        provider_reference="REF-9",
        assurance_level="L5",
        app_ref="nexo", display_name="Cliente X",
        actor="admin")
    assert r["registered"] is True
    assert r["reference"]["provider"] == "RNPN"
    r2 = uc.execute(zid="", provider="RNPN")
    assert r2["registered"] is False
    r3 = uc.execute(zid="ZID-2", provider="FAKE")
    assert r3["registered"] is False
    v = ValidateIdentityRecordUseCase(val).execute(
        zid="ZID-TEST-100", provider="LOGIN_SV")
    assert v["valid"] is True
    assert len(v["row_ids"]) == 3
    print("OK identidad use cases: registro validado + auditoria")

def test_credentials_lifecycle(tmp_path) -> None:
    db, clock = _db(tmp_path, "cr.db")
    mgr = NexoCredentialManager(db, clock)
    aud = NexoIdentityAudit(db, clock)
    uc = ManageCredentialsUseCase(mgr, aud)
    r = uc.execute(action="issue",
        zid="ZID-TEST-100",
        credential_type="FINANCIAL",
        issuer="ZYRA", reference="cred-ref-1")
    cid = r["credential"]["cred_id"]
    v = uc.execute(action="verify", cred_id=cid)
    assert v["result"]["valid"] is True
    with pytest.raises(ValueError):
        uc.execute(action="issue", zid="",
                   credential_type="X",
                   issuer="Y")
    uc.execute(action="revoke", cred_id=cid,
        reason="comprometida", actor="admin")
    v2 = uc.execute(action="verify", cred_id=cid)
    assert v2["result"]["valid"] is False
    assert "revocada" in v2["result"]["reason"]
    creds = mgr.creds_of("ZID-TEST-100")
    assert len(creds) == 1
    assert creds[0]["status"] == "REVOKED"
    h = aud.history_of("ZID-TEST-100")
    actions = [x["action"] for x in h]
    assert "CRED_ISSUED" in actions
    assert "CRED_REVOKED" in actions
    print("OK credenciales: emitir->verificar->revocar + auditoria")
