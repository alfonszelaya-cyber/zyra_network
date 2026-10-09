"""Tipos de escenario del motor de simulacion (LAB-CORE)."""

from enum import Enum


class ScenarioType(str, Enum):
    """Escenarios comparables A/B/C definidos por el propietario."""

    A = "A"
    B = "B"
    C = "C"

    @classmethod
    def validar(cls, valor: str) -> "ScenarioType":
        """Convierte y valida un texto a ScenarioType (A, B o C)."""
        if not isinstance(valor, str):
            raise ValueError("El tipo de escenario debe ser texto: A, B o C.")
        limpio = valor.strip().upper()
        try:
            return cls(limpio)
        except ValueError:
            raise ValueError(
                "Tipo de escenario invalido: " + repr(valor) + ". Use A, B o C."
            )
