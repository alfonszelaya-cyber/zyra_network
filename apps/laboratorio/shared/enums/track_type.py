"""Tipos de pista del eje TIEMPO (timeline 4D)."""
from enum import Enum


class TrackType(str, Enum):
    POSICION = "posicion"
    ROTACION = "rotacion"
    ESCALA = "escala"
    VISIBILIDAD = "visibilidad"
    LUZ = "luz"
    CAMARA = "camara"
    COLOR = "color"

    @classmethod
    def validar(cls, valor: str) -> "TrackType":
        if not isinstance(valor, str):
            raise ValueError("El tipo de pista debe ser texto.")
        limpio = valor.strip().lower()
        try:
            return cls(limpio)
        except ValueError:
            validos = ", ".join(t.value for t in cls)
            raise ValueError("Pista invalida: " + repr(valor) + ". Validas: " + validos)
