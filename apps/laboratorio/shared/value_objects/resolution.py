"""Resolucion de imagen/render (pixeles validados)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Resolucion:
    """Resolucion en pixeles con limites de produccion."""

    ancho: int
    alto: int

    MINIMO = 16
    MAXIMO = 8192

    def __post_init__(self):
        if isinstance(self.ancho, bool) or isinstance(self.alto, bool):
            raise ValueError("Resolucion debe ser entera en pixeles.")
        if not isinstance(self.ancho, int) or not isinstance(self.alto, int):
            raise ValueError("Resolucion debe ser entera en pixeles.")
        if not (self.MINIMO <= self.ancho <= self.MAXIMO):
            raise ValueError(
                "ancho fuera de rango 16-8192: " + str(self.ancho)
            )
        if not (self.MINIMO <= self.alto <= self.MAXIMO):
            raise ValueError(
                "alto fuera de rango 16-8192: " + str(self.alto)
            )

    @property
    def total_pixeles(self) -> int:
        """Cantidad total de pixeles."""
        return self.ancho * self.alto

    @property
    def relacion_aspecto(self) -> float:
        """Relacion ancho/alto redondeada."""
        return round(self.ancho / self.alto, 4)

    @classmethod
    def hd(cls) -> "Resolucion":
        """1920x1080."""
        return cls(1920, 1080)

    @classmethod
    def cuatro_k(cls) -> "Resolucion":
        """3840x2160."""
        return cls(3840, 2160)
