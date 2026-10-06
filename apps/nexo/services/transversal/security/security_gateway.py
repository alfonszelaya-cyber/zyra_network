
"""Gateway NEXO -> seguridad transversal (regla 69).

Delegacion fina a ApiKeyManager/hardening inyectados.
Sin motor: not_configured honesto."""
from __future__ import annotations

class NexoSecurityGateway:
    """Adaptador de seguridad NEXO."""

    def __init__(self, api_keys=None):
        self._keys = api_keys

    @property
    def mode(self) -> str:
        return ("shared_security"
                if self._keys is not None
                else "not_configured")

    def check_api_key(self, key) -> dict:
        if self._keys is not None:
            for name in ("verify", "validate",
                         "check", "authenticate"):
                m = getattr(self._keys, name, None)
                if callable(m):
                    try:
                        return {"status": "checked",
                                "result": bool(m(key))}
                    except Exception:
                        continue
        return {"status": "not_configured",
                "reason": "ApiKeyManager no inyectado"}
