"""Matematica geometrica compartida (los objetos viven en value_objects)."""

import math

from apps.laboratorio.shared.value_objects.geometry import Point3D, Vector3D


def punto_medio(a: Point3D, b: Point3D) -> Point3D:
    """Punto exactamente en medio entre dos puntos."""
    return Point3D((a.x + b.x) / 2.0, (a.y + b.y) / 2.0, (a.z + b.z) / 2.0)


def vector_entre(origen: Point3D, destino: Point3D) -> Vector3D:
    """Vector que va de origen a destino."""
    return Vector3D(
        destino.x - origen.x, destino.y - origen.y, destino.z - origen.z
    )


def angulo_entre(u: Vector3D, v: Vector3D) -> float:
    """Angulo en radianes entre dos vectores."""
    lu = u.longitud()
    lv = v.longitud()
    if lu == 0.0 or lv == 0.0:
        raise ValueError("No hay angulo con vectores de longitud cero.")
    coseno = u.producto_punto(v) / (lu * lv)
    coseno = max(-1.0, min(1.0, coseno))
    return math.acos(coseno)


def distancia(a: Point3D, b: Point3D) -> float:
    """Distancia entre dos puntos."""
    return a.distancia_a(b)
