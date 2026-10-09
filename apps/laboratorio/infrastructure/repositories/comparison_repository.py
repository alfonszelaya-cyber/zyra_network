"""Repositorio de comparaciones."""
from apps.laboratorio.domain.comparison import Comparacion
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class ComparisonRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("ComparisonRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> Comparacion:
        if not isinstance(entidad, Comparacion):
            raise ValueError("Se esperaba una Comparacion.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> Comparacion:
        comparacion = self.obtener_por_id(id_entidad)
        if comparacion is None:
            raise EntidadNoEncontradaError("Comparacion no encontrada.", str(id_entidad))
        return comparacion

    def listar_por_proyectos(self, proyecto_ids) -> list:
        return self._store.listar_por_proyectos(list(proyecto_ids))
