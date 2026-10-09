"""Repositorio de blueprints."""
from apps.laboratorio.domain.design import Blueprint
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class DesignRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("DesignRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> Blueprint:
        if not isinstance(entidad, Blueprint):
            raise ValueError("Se esperaba un Blueprint.")
        if not entidad.componentes:
            raise ValueError("Un blueprint sin componentes no se guarda.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> Blueprint:
        bp = self.obtener_por_id(id_entidad)
        if bp is None:
            raise EntidadNoEncontradaError("Blueprint no encontrado.", str(id_entidad))
        return bp

    def listar_por_proyectos(self, proyecto_ids) -> list:
        return self._store.listar_por_proyectos(list(proyecto_ids))
