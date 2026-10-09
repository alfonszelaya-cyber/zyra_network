"""Repositorio de auditoria (append-only, filas tipadas como dict)."""


class AuditoriaRepository:
    """Facade de AuditStore para la capa de aplicacion."""

    def __init__(self, store):
        if store is None:
            raise ValueError("AuditoriaRepository requiere su store.")
        self._store = store

    def registrar(self, actor_zid: str, accion: str, recurso: str, resultado: str, detalle: dict = None) -> int:
        """Registra un hecho auditado y devuelve su id."""
        return self._store.registrar(actor_zid, accion, recurso, resultado, detalle)

    def listar(self, limite: int = 50, offset: int = 0) -> list:
        """Lista la auditoria reciente."""
        return self._store.listar(limite, offset)
