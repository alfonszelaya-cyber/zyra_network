"""Repositorio del historial (append-only)."""
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.shared.interfaces.repository import Repositorio


class HistorialRepository(Repositorio):
    """Alta y consulta del historial; sin actualizar ni eliminar."""

    def __init__(self, store):
        if store is None:
            raise ValueError("HistorialRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> EntradaHistorial:
        """Registra una entrada nueva de historial."""
        if not isinstance(entidad, EntradaHistorial):
            raise ValueError("Se esperaba una EntradaHistorial.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        """El historial no expone busqueda por id individual."""
        raise ValueError("El historial se consulta por proyecto, no por id.")

    def listar(self, filtros=None, limite: int = 50, offset: int = 0) -> list:
        """Lista por proyecto_id (filtro requerido)."""
        filtros = filtros or {}
        if "proyecto_id" not in filtros:
            raise ValueError("listar requiere filtro proyecto_id.")
        return self._store.listar_por_proyecto(
            str(filtros["proyecto_id"]), limite, offset
        )

    def actualizar(self, entidad):
        """El historial es append-only."""
        raise ValueError("El historial no se actualiza.")

    def eliminar(self, id_entidad):
        """El historial es append-only."""
        raise ValueError("El historial no se elimina.")
