"""Calibrador manual: homografia REAL por DLT (8x8 gaussiano)."""
from apps.laboratorio.shared.exceptions.pipeline_errors import (
    SuperficieNoCalibradaError,
)

EPS = 1e-9


def resolver_lineal(matriz: list, vector: list) -> list:
    """Eliminacion gaussiana con pivoteo parcial."""
    n = len(vector)
    m = [fila[:] + [vector[i]] for i, fila in enumerate(matriz)]
    for col in range(n):
        pivote = max(range(col, n), key=lambda f: abs(m[f][col]))
        if abs(m[pivote][col]) < EPS:
            raise ValueError("Sistema singular: esquinas degeneradas.")
        m[col], m[pivote] = m[pivote], m[col]
        piv = m[col][col]
        for k in range(col, n + 1):
            m[col][k] /= piv
        for f in range(n):
            if f == col:
                continue
            factor = m[f][col]
            if factor == 0.0:
                continue
            for k in range(col, n + 1):
                m[f][k] -= factor * m[col][k]
    return [m[i][n] for i in range(n)]


def aplicar(H: list, x: float, y: float) -> tuple:
    """Aplica la homografia H a un punto (x, y)."""
    w = H[6] * x + H[7] * y + H[8]
    if abs(w) < EPS:
        raise ValueError("Punto en el infinito proyectivo.")
    return (
        (H[0] * x + H[1] * y + H[2]) / w,
        (H[3] * x + H[4] * y + H[5]) / w,
    )


def invertir3x3(H: list) -> list:
    """Inversa de la homografia por adjunta / determinante."""
    a, b, c, d, e, f, g, h, i = H
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < EPS:
        raise ValueError("Homografia no invertible.")
    return [
        (e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det,
        (f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det,
        (d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det,
    ]


class CalibradorManual:
    """Calcula la homografia fuente->superficie desde 4 esquinas."""

    def capacidades(self) -> dict:
        return {
            "metodo": "DLT con 4 pares de puntos (8x8 gauss)",
            "verificacion": "round-trip de esquinas < 1e-6",
        }

    def calibrar(self, esquinas_destino: list, ancho_origen: int, alto_origen: int) -> list:
        if not isinstance(esquinas_destino, list) or len(esquinas_destino) != 4:
            raise ValueError("Se requieren exactamente 4 esquinas.")
        if ancho_origen < 16 or alto_origen < 16:
            raise ValueError("Dimensiones de origen invalidas.")
        origen = [
            (0.0, 0.0), (float(ancho_origen), 0.0),
            (float(ancho_origen), float(alto_origen)), (0.0, float(alto_origen)),
        ]
        destino = []
        for punto in esquinas_destino:
            if not isinstance(punto, (list, tuple)) or len(punto) != 2:
                raise ValueError("Cada esquina debe ser [x, y].")
            destino.append((float(punto[0]), float(punto[1])))
        matriz = []
        vector = []
        for (x, y), (u, v) in zip(origen, destino):
            matriz.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
            vector.append(u)
            matriz.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
            vector.append(v)
        h = resolver_lineal(matriz, vector)
        H = [h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7], 1.0]
        for (x, y), (u, v) in zip(origen, destino):
            pu, pv = aplicar(H, x, y)
            if abs(pu - u) > 1e-6 or abs(pv - v) > 1e-6:
                raise SuperficieNoCalibradaError(
                    "La homografia no reproduce las esquinas."
                )
        return H
