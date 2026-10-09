"""Color RGBA inmutable con componentes normalizadas (0.0 a 1.0)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Color:
    """Color RGBA usado por materiales, luces y renders."""

    r: float = 1.0
    g: float = 1.0
    b: float = 1.0
    a: float = 1.0

    def __post_init__(self):
        for nombre in ("r", "g", "b", "a"):
            valor = getattr(self, nombre)
            if not 0.0 <= valor <= 1.0:
                raise ValueError(
                    "Componente " + nombre + " fuera de rango: "
                    + str(valor) + ". Debe estar entre 0.0 y 1.0."
                )

    @classmethod
    def desde_rgb255(cls, r: int, g: int, b: int, a: int = 255) -> "Color":
        """Crea un Color desde componentes enteras 0-255."""
        for nombre, valor in (("r", r), ("g", g), ("b", b), ("a", a)):
            if not 0 <= valor <= 255:
                raise ValueError(
                    "Componente " + nombre
                    + " fuera de rango 0-255: " + str(valor)
                )
        return cls(r / 255.0, g / 255.0, b / 255.0, a / 255.0)

    def a_rgb255(self) -> tuple:
        """Devuelve (r, g, b) enteras en 0-255."""
        return (
            round(self.r * 255),
            round(self.g * 255),
            round(self.b * 255),
        )

    def a_hex(self) -> str:
        """Devuelve el color como texto #RRGGBB."""
        r, g, b = self.a_rgb255()
        return "#" + format(r, "02X") + format(g, "02X") + format(b, "02X")

    @classmethod
    def negro(cls) -> "Color":
        """Color negro opaco."""
        return cls(0.0, 0.0, 0.0, 1.0)

    @classmethod
    def blanco(cls) -> "Color":
        """Color blanco opaco."""
        return cls(1.0, 1.0, 1.0, 1.0)
