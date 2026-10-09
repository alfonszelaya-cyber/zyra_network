"""Esquema de creacion de escenario (borde HTTP)."""

from apps.laboratorio.validators.business.scenario_validator import (
    validar_datos_escenario,
)


class SchemaCrearEscenario:
    @classmethod
    def validar(cls, datos) -> dict:
        return validar_datos_escenario(datos)
