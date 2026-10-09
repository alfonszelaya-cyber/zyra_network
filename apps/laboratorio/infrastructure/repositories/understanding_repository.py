"""Repositorio de comprensiones (alta y lectura)."""
from apps.laboratorio.domain.understanding import Comprension
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class UnderstandingRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("UnderstandingRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> Comprension:
        if not isinstance(entidad, Comprension):
            raise ValueError("Se esperaba una Comprension.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> Comprension:
        comp = self.obtener_por_id(id_entidad)
        if comp is None:
            raise EntidadNoEncontradaError("Comprension no encontrada.", str(id_entidad))
        return comp

    def obtener_por_entrada(self, entrada_id):
        return self._store.obtener_por_entrada(str(entrada_id))

    def listar_por_proyectos(self, proyecto_ids) -> list:
        return self._store.listar_por_proyectos(list(proyecto_ids))
