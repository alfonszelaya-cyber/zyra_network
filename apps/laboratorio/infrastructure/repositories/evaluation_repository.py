"""Repositorio de Evaluaciones (solo alta y lectura: inmutables)."""
from apps.laboratorio.domain.evaluation import Evaluacion
from apps.laboratorio.shared.interfaces.repository import Repositorio


class EvaluationRepository(Repositorio):
    """Alta y consulta de evaluaciones; sin actualizar ni eliminar."""

    def __init__(self, store):
        if store is None:
            raise ValueError("EvaluationRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> Evaluacion:
        """Persiste una evaluacion nueva."""
        if not isinstance(entidad, Evaluacion):
            raise ValueError("Se esperaba una Evaluacion.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        """Devuelve la Evaluacion o None."""
        return self._store.obtener(str(id_entidad))

    def listar(self, filtros=None, limite: int = 20, offset: int = 0) -> list:
        """Lista por escenario_id o proyecto_id."""
        filtros = filtros or {}
        if "escenario_id" in filtros:
            return self._store.listar_por_escenario(
                str(filtros["escenario_id"]), limite, offset
            )
        if "proyecto_id" in filtros:
            return self._store.listar_por_proyecto(
                str(filtros["proyecto_id"]), limite, offset
            )
        raise ValueError("listar requiere escenario_id o proyecto_id.")

    def actualizar(self, entidad):
        """Las evaluaciones son inmutables por diseño."""
        raise ValueError("Las evaluaciones no se actualizan: son inmutables.")

    def eliminar(self, id_entidad):
        """Las evaluaciones son inmutables por diseño."""
        raise ValueError("Las evaluaciones no se eliminan: son inmutables.")
