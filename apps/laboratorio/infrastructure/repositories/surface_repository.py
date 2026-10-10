"""Repositorio de superficies (propietario estricto)."""
from apps.laboratorio.domain.surface import Superficie
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class SurfaceRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("SurfaceRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> Superficie:
        if not isinstance(entidad, Superficie):
            raise ValueError("Se esperaba una Superficie.")
        self._store.insertar(entidad)
        return entidad

    def obtener_de(self, zid: str, id_entidad):
        superficie = self._store.obtener(str(id_entidad))
        if superficie is None or superficie.propietario_zid != str(zid):
            return None
        return superficie

    def obtener_exigir_de(self, zid: str, id_entidad) -> Superficie:
        superficie = self.obtener_de(zid, id_entidad)
        if superficie is None:
            raise EntidadNoEncontradaError(
                "Superficie no encontrada para este usuario.", str(id_entidad)
            )
        return superficie

    def actualizar_calibracion(self, entidad) -> Superficie:
        if not isinstance(entidad, Superficie):
            raise ValueError("Se esperaba una Superficie.")
        if not self._store.actualizar_calibracion(entidad):
            raise EntidadNoEncontradaError("Superficie no encontrada.", str(entidad.id))
        return entidad

    def listar_por_propietario(self, zid: str) -> list:
        return self._store.listar_por_propietario(zid)
