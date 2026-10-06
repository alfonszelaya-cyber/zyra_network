
"""Nexo Biometric Adapter (regla 69 + 63). Delega la
verificacion a la Red. Jamas guarda plantillas
biometricas locales. Fail-closed."""
from __future__ import annotations

class NexoBiometricAdapter:
    """Adaptador biometrico (fail-closed)."""

    def __init__(self, security_engine=None):
        self._eng = security_engine

    @property
    def mode(self) -> str:
        return ("shared_security"
                if self._eng is not None
                else "not_configured")

    def verify(self, *, zid, reference) -> dict:
        if self._eng is None:
            return {"verified": False,
                    "fail_closed": True,
                    "reason": "motor no inyectado"}
        for name in ("verify", "verify_face",
                     "match"):
            m = getattr(self._eng, name, None)
            if callable(m):
                try:
                    r = m(zid=zid,
                          reference=reference)
                    if isinstance(r, dict):
                        r.setdefault(
                            "fail_closed", False)
                        return r
                    return {"verified": bool(r),
                            "fail_closed": False}
                except TypeError:
                    continue
                except Exception as e:
                    return {"verified": False,
                            "fail_closed": True,
                            "reason": str(e)[:200]}
        return {"verified": False,
                "fail_closed": True,
                "reason": "motor sin metodo verify"}
