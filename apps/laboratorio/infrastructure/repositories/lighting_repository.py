"""Repositorio de programas de luz (uno por escena)."""
from apps.laboratorio.domain.lighting import ProgramaLuz
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError


class LightingRepository:
    def __init__(self, store):
        if store is None:
            raise ValueError("LightingRepository requiere su store.")
        self._store = store

    def agregar(self, entidad) -> ProgramaLuz:
        if not isinstance(entidad, ProgramaLuz):
            raise ValueError("Se esperaba un ProgramaLuz.")
        if self._store.obtener_por_escena(str(entidad.escena_id)) is not None:
            raise ValueError("La escena ya tiene un programa de luz.")
        if not entidad.pasos:
            raise ValueError("El programa de luz requiere al menos un paso.")
        self._store.insertar(entidad)
        return entidad

    def obtener_por_escena(self, escena_id):
        return self._store.obtener_por_escena(str(escena_id))

    def obtener_exigir_por_escena(self, escena_id) -> ProgramaLuz:
        programa = self.obtener_por_escena(escena_id)
        if programa is None:
            raise EntidadNoEncontradaError(
                "La escena no tiene programa de luz.", str(escena_id)
            )
        return programa
