"""Repositorio de zonas de interaccion (varias por escena)."""
from apps.laboratorio.domain.interaction import ZonaInteraccion
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class InteractionRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("InteractionRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> ZonaInteraccion:
        if not isinstance(entidad, ZonaInteraccion):
            raise ValueError("Se esperaba una ZonaInteraccion.")
        if self._store.contar_por_escena(str(entidad.escena_id)) >= 50:
            raise ValueError("Maximo 50 interacciones por escena.")
        self._store.insertar(entidad)
        return entidad

    def listar_por_escena(self, escena_id) -> list:
        return self._store.listar_por_escena(str(escena_id))

    def contar_por_escena(self, escena_id) -> int:
        return self._store.contar_por_escena(str(escena_id))

    def obtener_exigir(self, escena_id) -> list:
        zonas = self.listar_por_escena(escena_id)
        if not zonas:
            raise EntidadNoEncontradaError(
                "La escena no tiene interacciones.", str(escena_id)
            )
        return zonas
