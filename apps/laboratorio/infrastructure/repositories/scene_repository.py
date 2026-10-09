"""Repositorio de escenas 3D."""
from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class SceneRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("SceneRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> Escena3D:
        if not isinstance(entidad, Escena3D):
            raise ValueError("Se esperaba una Escena3D.")
        if not entidad.es_renderizable:
            raise ValueError("Una escena sin objetos no se guarda.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> Escena3D:
        escena = self.obtener_por_id(id_entidad)
        if escena is None:
            raise EntidadNoEncontradaError("Escena no encontrada.", str(id_entidad))
        return escena

    def listar_por_proyecto(self, proyecto_id) -> list:
        return self._store.listar_por_proyecto(str(proyecto_id))

    def listar_por_proyectos(self, proyecto_ids) -> list:
        return self._store.listar_por_proyectos(list(proyecto_ids))
