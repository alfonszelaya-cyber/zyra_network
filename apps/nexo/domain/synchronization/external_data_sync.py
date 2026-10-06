
"""Nexo External Sync - adaptador a integrations de la
Red (regla 69). Sin cliente -> not_configured."""
from __future__ import annotations

class NexoExternalSync:
    """Sweep de fuentes externas via integrations."""

    def __init__(self, client=None):
        self._client = client

    @property
    def mode(self) -> str:
        return ("integrations"
                if self._client is not None
                else "not_configured")

    def sweep(self, source) -> dict:
        if self._client is None:
            return {"status": "not_configured",
                    "reason": "client no inyectado"
                              " (wiring NG12)"}
        for name in ("sweep", "fetch",
                     "get_source"):
            m = getattr(self._client, name, None)
            if callable(m):
                try:
                    r = m(source)
                    return {"status": "ok",
                            "result": (r if
                                       isinstance(r, dict)
                                       else
                                       {"raw": str(r)})}
                except TypeError:
                    continue
                except Exception as e:
                    return {"status": "error",
                            "error": str(e)[:200]}
        return {"status": "error",
                "error": "cliente sin metodo sweep"}
