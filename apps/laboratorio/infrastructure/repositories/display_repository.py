"""Repositorio de destinos de salida (propietario estricto)."""
from apps.laboratorio.domain.display import DestinoSalida
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class DisplayRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("DisplayRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> DestinoSalida:
        if not isinstance(entidad, DestinoSalida):
            raise ValueError("Se esperaba un DestinoSalida.")
        self._store.insertar(entidad)
        return entidad

    def obtener_de(self, zid: str, id_entidad):
        destino = self._store.obtener(str(id_entidad))
        if destino is None or destino.propietario_zid != str(zid):
            return None
        return destino

    def obtener_exigir_de(self, zid: str, id_entidad) -> DestinoSalida:
        destino = self.obtener_de(zid, id_entidad)
        if destino is None:
            raise EntidadNoEncontradaError(
                "Salida no encontrada para este usuario.", str(id_entidad)
            )
        return destino

    def listar_por_propietario(self, zid: str) -> list:
        return self._store.listar_por_propietario(zid)
