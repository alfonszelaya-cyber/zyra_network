"""Repositorio de simulaciones de evolucion."""
from apps.laboratorio.domain.simulation import SimulacionEvolucion
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class SimulationRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("SimulationRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> SimulacionEvolucion:
        if not isinstance(entidad, SimulacionEvolucion):
            raise ValueError("Se esperaba una SimulacionEvolucion.")
        if not entidad.serie:
            raise ValueError("Una simulacion sin serie no se guarda.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        return self._store.obtener(str(id_entidad))

    def listar_por_proyectos(self, proyecto_ids) -> list:
        return self._store.listar_por_proyectos(list(proyecto_ids))
