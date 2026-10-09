"""Repositorio de activos de biblioteca."""
from apps.laboratorio.domain.asset import Activo
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class AssetRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("AssetRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> Activo:
        if not isinstance(entidad, Activo):
            raise ValueError("Se esperaba un Activo.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> Activo:
        activo = self.obtener_por_id(id_entidad)
        if activo is None:
            raise EntidadNoEncontradaError("Activo no encontrado.", str(id_entidad))
        return activo

    def listar_por_propietario(self, zid: str) -> list:
        return self._store.listar_por_propietario(zid)

    def buscar_por_etiqueta(self, zid: str, etiqueta: str) -> list:
        return [
            a for a in self._store.listar_por_propietario(zid, 500)
            if a.tiene_etiqueta(etiqueta)
        ]
