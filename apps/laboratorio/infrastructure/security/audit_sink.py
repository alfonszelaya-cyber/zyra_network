"""Puerta de auditoria para toda operacion sensible."""

from apps.laboratorio.shared.helpers.json_helpers import a_json


class AuditoriaSink:
    """Registra quien hizo que, sobre que recurso y con que resultado."""

    def __init__(self, repositorio):
        if repositorio is None:
            raise ValueError("AuditoriaSink requiere su repositorio.")
        self._repo = repositorio

    def registrar(self, identidad, accion: str, recurso: str, resultado: str, detalle: dict = None) -> int:
        actor = identidad.zid if identidad is not None and hasattr(identidad, "zid") else "anonimo"
        return self._repo.registrar(actor, accion, recurso, resultado, detalle)

    def registrar_error(self, identidad, accion: str, recurso: str, exc: Exception) -> int:
        detalle = {"error": type(exc).__name__, "mensaje": a_json({"m": str(exc)[:300]})}
        return self.registrar(identidad, accion, recurso, "error", detalle)
