"""Repositorio de Proyectos: dominio <-> store con errores de dominio."""
from apps.laboratorio.domain.project import Proyecto
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError
from apps.laboratorio.shared.interfaces.repository import Repositorio


class ProyectoRepository(Repositorio):
    """Implementa el puerto Repositorio para el agregado Proyecto."""

    def __init__(self, store):
        if store is None:
            raise ValueError("ProyectoRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> Proyecto:
        """Persiste un proyecto nuevo validando su tipo."""
        if not isinstance(entidad, Proyecto):
            raise ValueError("Se esperaba un Proyecto.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        """Devuelve el Proyecto o None."""
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> Proyecto:
        """Devuelve el Proyecto o lanza EntidadNoEncontradaError."""
        proyecto = self.obtener_por_id(id_entidad)
        if proyecto is None:
            raise EntidadNoEncontradaError("Proyecto no encontrado.", str(id_entidad))
        return proyecto

    def listar(self, filtros=None, limite: int = 20, offset: int = 0) -> list:
        """Lista por propietario_zid (filtro requerido)."""
        filtros = filtros or {}
        if "propietario_zid" not in filtros:
            raise ValueError("listar requiere filtro propietario_zid.")
        return self._store.listar_por_propietario(
            filtros["propietario_zid"], limite, offset
        )

    def actualizar(self, entidad) -> Proyecto:
        """Actualiza exigiendo existencia previa."""
        if not isinstance(entidad, Proyecto):
            raise ValueError("Se esperaba un Proyecto.")
        if not self._store.actualizar(entidad):
            raise EntidadNoEncontradaError("Proyecto no encontrado.", str(entidad.id))
        return entidad

    def eliminar(self, id_entidad) -> bool:
        """Elimina por id."""
        return self._store.eliminar(str(id_entidad))
