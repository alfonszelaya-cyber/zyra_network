"""Repositorio de lineas de tiempo (una por escena)."""
from apps.laboratorio.domain.timeline import LineaTiempo
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class TimelineRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("TimelineRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> LineaTiempo:
        if not isinstance(entidad, LineaTiempo):
            raise ValueError("Se esperaba una LineaTiempo.")
        if self._store.obtener_por_escena(str(entidad.escena_id)) is not None:
            raise ValueError("La escena ya tiene una linea de tiempo.")
        if not entidad.pistas:
            raise ValueError("La linea de tiempo requiere al menos una pista.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_escena(self, escena_id):
        return self._store.obtener_por_escena(str(escena_id))

    def obtener_exigir_por_escena(self, escena_id) -> LineaTiempo:
        linea = self.obtener_por_escena(escena_id)
        if linea is None:
            raise EntidadNoEncontradaError(
                "La escena no tiene linea de tiempo.", str(escena_id)
            )
        return linea
