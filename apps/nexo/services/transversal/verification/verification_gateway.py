
"""Gateway NEXO -> verificacion/credenciales de la Red.

Usa NexoLink inyectado para /verification/credentials
(credenciales financieras verificables). Sin link:
not_configured honesto (nunca falsos OK)."""
from __future__ import annotations

class NexoVerificationGateway:
    """Credenciales financieras via Red ZYRA."""

    def __init__(self, link=None):
        self._link = link

    @property
    def mode(self) -> str:
        return ("nexo_link"
                if self._link is not None
                else "not_configured")

    def request_financial_credential(self, *,
                                     company_id,
                                     payload=None) -> dict:
        if self._link is not None:
            for name in ("request_credential",
                         "financial_credential",
                         "credentials",
                         "request_financial_credential"):
                m = getattr(self._link, name, None)
                if callable(m):
                    try:
                        r = m(company_id=company_id,
                              payload=payload)
                    except TypeError:
                        r = m(company_id)
                    return {"status": "requested",
                            "via": self.mode,
                            "result": (r if
                                       isinstance(r, dict)
                                       else
                                       {"raw": str(r)})}
        return {"status": "not_configured",
                "reason": "NexoLink no inyectado "
                          "(wiring pendiente NG12)"}
