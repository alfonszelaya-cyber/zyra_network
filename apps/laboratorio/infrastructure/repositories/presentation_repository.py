"""Repositorio de presentaciones."""
from apps.laboratorio.domain.presentation import Presentacion
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class PresentationRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("PresentationRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> Presentacion:
        if not isinstance(entidad, Presentacion):
            raise ValueError("Se esperaba una Presentacion.")
        if not entidad.pasos:
            raise ValueError("Una presentacion sin pasos no se guarda.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> Presentacion:
        presentacion = self.obtener_por_id(id_entidad)
        if presentacion is None:
            raise EntidadNoEncontradaError("Presentacion no encontrada.", str(id_entidad))
        return presentacion

    def actualizar_sello(self, entidad) -> Presentacion:
        if not isinstance(entidad, Presentacion):
            raise ValueError("Se esperaba una Presentacion.")
        if not self._store.actualizar_sello(entidad):
            raise EntidadNoEncontradaError("Presentacion no encontrada.", str(entidad.id))
        return entidad

    def listar_por_proyectos(self, proyecto_ids) -> list:
        return self._store.listar_por_proyectos(list(proyecto_ids))
