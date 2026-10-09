"""Repositorio de exportaciones."""
from apps.laboratorio.domain.export_bundle import Exportacion
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class ExportRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("ExportRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> Exportacion:
        if not isinstance(entidad, Exportacion):
            raise ValueError("Se esperaba una Exportacion.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> Exportacion:
        exportacion = self.obtener_por_id(id_entidad)
        if exportacion is None:
            raise EntidadNoEncontradaError("Exportacion no encontrada.", str(id_entidad))
        return exportacion

    def listar_por_proyectos(self, proyecto_ids) -> list:
        return self._store.listar_por_proyectos(list(proyecto_ids))
