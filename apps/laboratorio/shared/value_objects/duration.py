"""Duracion temporal en segundos (eje TIEMPO del 4D)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Duracion:
    """Intervalo de tiempo en segundos, de 0.001 a 24 horas."""

    segundos: float

    MIN = 0.001
    MAX = 86400.0

    def __post_init__(self):
        if isinstance(self.segundos, bool) or not isinstance(
            self.segundos, (int, float)
        ):
            raise ValueError("La duracion debe ser numerica en segundos.")
        valor = float(self.segundos)
        if not (self.MIN <= valor <= self.MAX):
            raise ValueError("Duracion fuera de rango: " + str(valor))

    @property
    def milisegundos(self) -> int:
        """Duracion en milisegundos enteros."""
        return int(round(self.segundos * 1000.0))

    def mas(self, otra: "Duracion") -> "Duracion":
        """Suma dos duraciones validando el maximo."""
        return Duracion(self.segundos + otra.segundos)

    @classmethod
    def desde_minutos(cls, minutos: float) -> "Duracion":
        """Crea una duracion desde minutos."""
        return cls(float(minutos) * 60.0)
