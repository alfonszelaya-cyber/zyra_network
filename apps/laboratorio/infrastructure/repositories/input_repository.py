"""Repositorio de entradas de captura."""
from apps.laboratorio.domain.input_capture import EntradaCaptura
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class InputRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("InputRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> EntradaCaptura:
        if not isinstance(entidad, EntradaCaptura):
            raise ValueError("Se esperaba una EntradaCaptura.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_id(self, id_entidad):
        return self._store.obtener(str(id_entidad))

    def obtener_exigir(self, id_entidad) -> EntradaCaptura:
        entrada = self.obtener_por_id(id_entidad)
        if entrada is None:
            raise EntidadNoEncontradaError("Entrada no encontrada.", str(id_entidad))
        return entrada

    def listar_por_proyecto(self, proyecto_id) -> list:
        return self._store.listar_por_proyecto(str(proyecto_id))

    def listar_por_proyectos(self, proyecto_ids) -> list:
        return self._store.listar_por_proyectos(list(proyecto_ids))
