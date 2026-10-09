"""Escalera de calidad fotoreal: de borrador a fotorreal."""
from enum import Enum


class RenderQuality(str, Enum):
    BORRADOR = "borrador"
    ALTA = "alta"
    TRES_D = "3d"
    FOTORREAL = "fotorreal"

    @classmethod
    def validar(cls, valor: str) -> "RenderQuality":
        if not isinstance(valor, str):
            raise ValueError("La calidad debe ser texto.")
        limpio = valor.strip().lower()
        try:
            return cls(limpio)
        except ValueError:
            validos = ", ".join(t.value for t in cls)
            raise ValueError("Calidad invalida: " + repr(valor) + ". Validas: " + validos)

    @classmethod
    def cadena(cls) -> list:
        """Orden oficial de la escalera fotoreal."""
        return [cls.BORRADOR.value, cls.ALTA.value, cls.TRES_D.value, cls.FOTORREAL.value]

    @property
    def orden(self) -> int:
        """Posicion en la escalera (0 = mas bajo)."""
        return cls.cadena().index(self.value)
