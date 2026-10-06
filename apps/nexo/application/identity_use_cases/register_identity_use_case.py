
from __future__ import annotations

class RegisterIdentityUseCase:
    """Valida y registra referencia de identidad
    (regla 63) + auditoria."""

    def __init__(self, validation, identity_registry,
                 identity_refs=None,
                 identity_audit=None):
        self._val = validation
        self._reg = identity_registry
        self._refs = identity_refs
        self._aud = identity_audit

    def execute(self, *, zid, provider,
                provider_reference="",
                assurance_level="L0",
                app_ref="",
                display_name="",
                expires_at=None,
                actor="") -> dict:
        v = self._val.validate_reference(
            zid=zid, provider=provider,
            expires_at=expires_at)
        if not v["valid"]:
            return {"registered": False,
                    "validation": v}
        user = self._reg.register(
            zid=zid, app_ref=app_ref,
            display_name=display_name)
        ref = None
        if self._refs is not None:
            ref = self._refs.register_reference(
                zid=zid, provider=provider,
                provider_reference=
                provider_reference,
                assurance_level=assurance_level,
                expires_at=expires_at)
        if self._aud is not None:
            self._aud.record(
                zid=zid,
                action="REGISTER_REFERENCE",
                actor=actor,
                detail="provider=" + provider)
        return {"registered": True,
                "user": user,
                "reference": ref}
