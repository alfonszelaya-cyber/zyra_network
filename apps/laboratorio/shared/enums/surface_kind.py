"""Tipos de superficie proyectable: cualquier superficie es valida."""
from enum import Enum


class SurfaceKind(str, Enum):
    PARED = "pared"
    PISO = "piso"
    TECHO = "techo"
    CURVA = "curva"
    FACHADA = "fachada"
    OBJETO = "objeto"
    MAQUETA = "maqueta"
    GRUPO = "grupo"

    @classmethod
    def validar(cls, valor: str) -> "SurfaceKind":
        if not isinstance(valor, str):
            raise ValueError("El tipo de superficie debe ser texto.")
        limpio = valor.strip().lower()
        try:
            return cls(limpio)
        except ValueError:
            validos = ", ".join(t.value for t in cls)
            raise ValueError("Superficie invalida: " + repr(valor) + ". Validas: " + validos)
