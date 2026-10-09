"""Tipos de entrada de captura (etapas DESCRIBIR a IMPORTAR)."""
from enum import Enum


class InputKind(str, Enum):
    TEXTO = "texto"
    FOTO = "foto"
    ESCANEO = "escaneo"
    MEDICION = "medicion"
    IMPORTACION = "importacion"

    @classmethod
    def validar(cls, valor: str) -> "InputKind":
        if not isinstance(valor, str):
            raise ValueError("El tipo de entrada debe ser texto.")
        limpio = valor.strip().lower()
        try:
            return cls(limpio)
        except ValueError:
            validos = ", ".join(t.value for t in cls)
            raise ValueError("Entrada invalida: " + repr(valor) + ". Validas: " + validos)
