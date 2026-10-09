"""Tipos de interaccion del canal INTERACCION del 4D."""
from enum import Enum


class InteractionKind(str, Enum):
    CLIC = "clic"
    SELECCION = "seleccion"
    CAMARA = "camara"
    FORMULARIO = "formulario"
    ZONA = "zona"
    TECLADO = "teclado"

    @classmethod
    def validar(cls, valor: str) -> "InteractionKind":
        if not isinstance(valor, str):
            raise ValueError("El tipo de interaccion debe ser texto.")
        limpio = valor.strip().lower()
        try:
            return cls(limpio)
        except ValueError:
            validos = ", ".join(t.value for t in cls)
            raise ValueError("Interaccion invalida: " + repr(valor) + ". Validas: " + validos)
