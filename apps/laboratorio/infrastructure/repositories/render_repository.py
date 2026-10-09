"""Repositorio de trabajos de render."""
from apps.laboratorio.domain.render import TrabajoRender
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class RenderRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("RenderRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> TrabajoRender:
        if not isinstance(entidad, TrabajoRender):
            raise ValueError("Se esperaba un TrabajoRender.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> TrabajoRender:
        render = self.obtener_por_id(id_entidad)
        if render is None:
            raise EntidadNoEncontradaError("Render no encontrado.", str(id_entidad))
        return render

    def listar_resumen_por_proyectos(self, proyecto_ids) -> list:
        """Lista sin blobs: metadata ligera para tablas y UI."""
        return self._store.listar_por_proyectos(list(proyecto_ids))
