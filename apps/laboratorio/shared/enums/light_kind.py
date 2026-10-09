"""Tipos de luz del canal LUZ del 4D."""
from enum import Enum


class LightKind(str, Enum):
    DIRECCIONAL = "direccional"
    PUNTUAL = "puntual"
    SPOT = "spot"
    AMBIENTE = "ambiente"
    AREA = "area"

    @classmethod
    def validar(cls, valor: str) -> "LightKind":
        if not isinstance(valor, str):
            raise ValueError("El tipo de luz debe ser texto.")
        limpio = valor.strip().lower()
        try:
            return cls(limpio)
        except ValueError:
            validos = ", ".join(t.value for t in cls)
            raise ValueError("Luz invalida: " + repr(valor) + ". Validas: " + validos)
