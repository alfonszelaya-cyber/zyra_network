"""Repositorio de Escenarios A/B/C."""
from apps.laboratorio.domain.scenario import Escenario
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError
from apps.laboratorio.shared.interfaces.repository import Repositorio


class ScenarioRepository(Repositorio):
    """Implementa el puerto Repositorio para escenarios."""

    def __init__(self, store):
        if store is None:
            raise ValueError("ScenarioRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> Escenario:
        """Persiste un escenario validando su tipo."""
        if not isinstance(entidad, Escenario):
            raise ValueError("Se esperaba un Escenario.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        """Devuelve el Escenario o None."""
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> Escenario:
        """Devuelve el Escenario o lanza EntidadNoEncontradaError."""
        escenario = self.obtener_por_id(id_entidad)
        if escenario is None:
            raise EntidadNoEncontradaError("Escenario no encontrado.", str(id_entidad))
        return escenario

    def listar(self, filtros=None, limite: int = 20, offset: int = 0) -> list:
        """Lista por proyecto_id (filtro requerido)."""
        filtros = filtros or {}
        if "proyecto_id" not in filtros:
            raise ValueError("listar requiere filtro proyecto_id.")
        return self._store.listar_por_proyecto(
            str(filtros["proyecto_id"]), limite, offset
        )

    def actualizar(self, entidad) -> Escenario:
        """Actualiza exigiendo existencia previa."""
        if not isinstance(entidad, Escenario):
            raise ValueError("Se esperaba un Escenario.")
        if not self._store.actualizar(entidad):
            raise EntidadNoEncontradaError("Escenario no encontrado.", str(entidad.id))
        return entidad

    def eliminar(self, id_entidad) -> bool:
        """Elimina por id."""
        return self._store.eliminar(str(id_entidad))
