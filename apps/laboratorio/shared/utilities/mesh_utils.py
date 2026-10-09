"""Utilidades de mallas 3D: bbox, triangulos e indices."""
from typing import Sequence, Tuple


def _vertice_valido(v) -> bool:
    if not isinstance(v, (tuple, list)) or len(v) != 3:
        return False
    for c in v:
        if isinstance(c, bool) or not isinstance(c, (int, float)):
            return False
    return True


def bounding_box(vertices: Sequence[Tuple[float, float, float]]) -> tuple:
    """Devuelve ((min_x,min_y,min_z), (max_x,max_y,max_z))."""
    if not vertices:
        raise ValueError("bounding_box requiere al menos un vertice.")
    for v in vertices:
        if not _vertice_valido(v):
            raise ValueError("Vertice invalido: " + repr(v))
    xs = [float(v[0]) for v in vertices]
    ys = [float(v[1]) for v in vertices]
    zs = [float(v[2]) for v in vertices]
    return ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def contar_triangulos(indices: Sequence[int]) -> int:
    """Cuenta triangulos: los indices deben venir en multiplos de 3."""
    if not indices or len(indices) % 3 != 0:
        raise ValueError("Indices deben venir en multiplos de 3.")
    return len(indices) // 3


def validar_indices(indices: Sequence[int], total_vertices: int) -> bool:
    """True si todo indice apunta a un vertice existente."""
    if total_vertices < 1:
        raise ValueError("total_vertices debe ser positivo.")
    for i in indices:
        if not isinstance(i, int) or isinstance(i, bool):
            raise ValueError("Indice no entero: " + repr(i))
        if not 0 <= i < total_vertices:
            raise ValueError("Indice fuera de rango: " + str(i))
    return True
