"""Repositorio de artefactos (alta y lectura)."""
from apps.laboratorio.domain.artifact import Artefacto
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class ArtifactRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("ArtifactRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> Artefacto:
        if not isinstance(entidad, Artefacto):
            raise ValueError("Se esperaba un Artefacto.")
        if not entidad.contenido:
            raise ValueError("Un artefacto sin contenido no se guarda.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> Artefacto:
        art = self.obtener_por_id(id_entidad)
        if art is None:
            raise EntidadNoEncontradaError("Artefacto no encontrado.", str(id_entidad))
        return art

    def listar_por_proyectos(self, proyecto_ids) -> list:
        return self._store.listar_por_proyectos(list(proyecto_ids))
