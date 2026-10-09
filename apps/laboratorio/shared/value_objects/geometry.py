"""Objetos de valor geometricos inmutables para el mundo 3D/4D."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Point3D:
    """Punto en el espacio 3D."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def sumar_vector(self, vector: "Vector3D") -> "Point3D":
        """Devuelve el punto desplazado por un vector."""
        return Point3D(self.x + vector.x, self.y + vector.y, self.z + vector.z)

    def distancia_a(self, otro: "Point3D") -> float:
        """Distancia euclidiana a otro punto."""
        return math.sqrt(
            (self.x - otro.x) ** 2
            + (self.y - otro.y) ** 2
            + (self.z - otro.z) ** 2
        )


@dataclass(frozen=True)
class Vector3D:
    """Vector (direccion y magnitud) en el espacio 3D."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, otro: "Vector3D") -> "Vector3D":
        return Vector3D(self.x + otro.x, self.y + otro.y, self.z + otro.z)

    def __sub__(self, otro: "Vector3D") -> "Vector3D":
        return Vector3D(self.x - otro.x, self.y - otro.y, self.z - otro.z)

    def escalar(self, factor: float) -> "Vector3D":
        """Multiplica el vector por un escalar."""
        return Vector3D(self.x * factor, self.y * factor, self.z * factor)

    def longitud(self) -> float:
        """Magnitud del vector."""
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

    def normalizar(self) -> "Vector3D":
        """Devuelve el vector con longitud 1.0."""
        magnitud = self.longitud()
        if magnitud == 0.0:
            raise ValueError("No se puede normalizar un vector de longitud cero.")
        return Vector3D(
            self.x / magnitud, self.y / magnitud, self.z / magnitud
        )

    def producto_punto(self, otro: "Vector3D") -> float:
        """Producto punto con otro vector."""
        return self.x * otro.x + self.y * otro.y + self.z * otro.z


@dataclass(frozen=True)
class Quaternion:
    """Orientacion 3D como quaternion (x, y, z, w)."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0

    def longitud(self) -> float:
        """Magnitud del quaternion."""
        return math.sqrt(
            self.x ** 2 + self.y ** 2 + self.z ** 2 + self.w ** 2
        )

    def normalizar(self) -> "Quaternion":
        """Devuelve el quaternion normalizado (rotacion valida)."""
        magnitud = self.longitud()
        if magnitud == 0.0:
            raise ValueError(
                "No se puede normalizar un quaternion de longitud cero."
            )
        return Quaternion(
            self.x / magnitud,
            self.y / magnitud,
            self.z / magnitud,
            self.w / magnitud,
        )
