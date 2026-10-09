"""Tipo de confianza con validacion 0.0 a 1.0."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Confianza:
    """Valor de confianza normalizado entre 0.0 y 1.0."""

    valor: float

    def __post_init__(self):
        if isinstance(self.valor, bool) or not isinstance(
            self.valor, (int, float)
        ):
            raise ValueError("La confianza debe ser numerica.")
        if not 0.0 <= float(self.valor) <= 1.0:
            raise ValueError(
                "La confianza debe estar entre 0.0 y 1.0: " + str(self.valor)
            )

    @property
    def porcentaje(self) -> float:
        """Confianza como porcentaje 0-100."""
        return round(float(self.valor) * 100.0, 2)

    @classmethod
    def alta(cls) -> "Confianza":
        """Confianza alta estandar (0.9)."""
        return cls(0.9)

    @classmethod
    def media(cls) -> "Confianza":
        """Confianza media estandar (0.6)."""
        return cls(0.6)

    @classmethod
    def baja(cls) -> "Confianza":
        """Confianza baja estandar (0.3)."""
        return cls(0.3)
