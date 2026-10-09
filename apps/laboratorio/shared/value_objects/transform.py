"""Transformacion 3D: posicion + orientacion + escala (inmutable)."""

from dataclasses import dataclass

from apps.laboratorio.shared.value_objects.geometry import (
    Point3D,
    Quaternion,
    Vector3D,
)


@dataclass(frozen=True)
class Transform:
    """Ubicacion completa de un objeto en la escena 3D."""

    posicion: Point3D = Point3D()
    orientacion: Quaternion = Quaternion()
    escala: Vector3D = Vector3D(1.0, 1.0, 1.0)

    def __post_init__(self):
        if self.escala.x == 0.0 or self.escala.y == 0.0 or self.escala.z == 0.0:
            raise ValueError("La escala no puede tener componentes en cero.")

    def trasladar(self, delta: Vector3D) -> "Transform":
        """Devuelve la transform movida por un vector."""
        return Transform(
            posicion=self.posicion.sumar_vector(delta),
            orientacion=self.orientacion,
            escala=self.escala,
        )

    def escalar_por(self, factor: float) -> "Transform":
        """Devuelve la transform escalada uniformemente."""
        if factor <= 0.0:
            raise ValueError("El factor de escala debe ser mayor que cero.")
        return Transform(
            posicion=self.posicion,
            orientacion=self.orientacion,
            escala=Vector3D(
                self.escala.x * factor,
                self.escala.y * factor,
                self.escala.z * factor,
            ),
        )
