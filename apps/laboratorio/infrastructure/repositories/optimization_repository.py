"""Repositorio de propuestas de optimizacion."""
from apps.laboratorio.domain.optimization import PropuestaOptimizacion
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class OptimizationRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("OptimizationRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> PropuestaOptimizacion:
        if not isinstance(entidad, PropuestaOptimizacion):
            raise ValueError("Se esperaba una PropuestaOptimizacion.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> PropuestaOptimizacion:
        propuesta = self.obtener_por_id(id_entidad)
        if propuesta is None:
            raise EntidadNoEncontradaError("Propuesta no encontrada.", str(id_entidad))
        return propuesta

    def actualizar_aplicada(self, entidad) -> PropuestaOptimizacion:
        if not isinstance(entidad, PropuestaOptimizacion):
            raise ValueError("Se esperaba una PropuestaOptimizacion.")
        if not self._store.actualizar_aplicada(entidad):
            raise EntidadNoEncontradaError("Propuesta no encontrada.", str(entidad.id))
        return entidad

    def listar_por_proyectos(self, proyecto_ids) -> list:
        return self._store.listar_por_proyectos(list(proyecto_ids))
