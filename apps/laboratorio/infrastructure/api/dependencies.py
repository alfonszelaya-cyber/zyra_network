"""Dependencias de proceso: monta el contenedor una sola vez."""
import os

from apps.laboratorio.registry.services.service_registry import construir_contenedor


class Dependencias:
    def __init__(self, contenedor):
        self._contenedor = contenedor

    @property
    def contenedor(self):
        return self._contenedor

    @classmethod
    def montar(cls, ruta_bd: str = None) -> "Dependencias":
        ruta = ruta_bd or os.environ.get("LAB_DB_RUTA", ":memory:")
        return cls(construir_contenedor(ruta))
