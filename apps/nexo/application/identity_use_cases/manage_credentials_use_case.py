
from __future__ import annotations

class ManageCredentialsUseCase:
    """Emite, verifica y revoca credenciales por
    referencia (regla 63)."""

    def __init__(self, credential_manager,
                 identity_audit=None):
        self._mgr = credential_manager
        self._aud = identity_audit

    def execute(self, *, action, zid="",
                credential_type="", issuer="",
                reference="", expires_at=None,
                cred_id="", reason="",
                actor="") -> dict:
        if action == "issue":
            c = self._mgr.issue(
                zid=zid,
                credential_type=credential_type,
                issuer=issuer,
                reference=reference,
                expires_at=expires_at)
            if self._aud is not None:
                self._aud.record(
                    zid=zid, action="CRED_ISSUED",
                    actor=actor,
                    detail=credential_type)
            return {"action": "issue",
                    "credential": c}
        if action == "verify":
            return {"action": "verify",
                    "result": self._mgr.verify(
                        cred_id)}
        if action == "revoke":
            c = self._mgr.revoke(
                cred_id=cred_id, reason=reason)
            if self._aud is not None:
                self._aud.record(
                    zid=c["zid"],
                    action="CRED_REVOKED",
                    actor=actor, detail=reason)
            return {"action": "revoke",
                    "credential": c}
        return {"action": action,
                "error": "accion desconocida"}
