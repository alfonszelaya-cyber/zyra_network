"""Destinos de salida de la Display Abstraction."""

from enum import Enum


class DisplayKind(str, Enum):
    """El mismo contenido puede salir por cualquiera de estos destinos."""

    PANTALLA = "pantalla"
    PROYECTOR = "proyector"
    HOLOGRAFICO = "holografico"
    LIGHT_FIELD = "light_field"
    AR = "ar"
    VR = "vr"
    FUTURO = "futuro"

    @classmethod
    def validar(cls, valor: str) -> "DisplayKind":
        """Convierte y valida un texto a DisplayKind."""
        if not isinstance(valor, str):
            raise ValueError("El tipo de salida debe ser texto.")
        limpio = valor.strip().lower()
        try:
            return cls(limpio)
        except ValueError:
            validos = ", ".join(t.value for t in cls)
            raise ValueError(
                "Tipo de salida invalido: " + repr(valor)
                + ". Validos: " + validos
            )
