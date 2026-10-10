"""Warper de perspectiva: warp REAL con salida normalizada."""
from apps.laboratorio.infrastructure.providers.calibrator_manual import (
    invertir3x3,
    aplicar,
)
from apps.laboratorio.infrastructure.providers.png_decoder import (
    decodificar_png_rgb,
)
from apps.laboratorio.infrastructure.providers.png_encoder import (
    encode_png_rgb,
)
from apps.laboratorio.shared.exceptions.pipeline_errors import (
    SuperficieNoCalibradaError,
)

FONDO = (15, 23, 42)


def _normalizar(buffer: bytearray, esperado: int) -> bytes:
    datos = bytes(buffer)
    if len(datos) == esperado:
        return datos
    if len(datos) < esperado:
        return datos + bytes(esperado - len(datos))
    return datos[:esperado]


def warpear(imagen_png: bytes, homografia: list, salida_ancho: int, salida_alto: int,
            origen_x: float = 0.0, origen_y: float = 0.0) -> bytes:
    """Warp por mapeo inverso. origen_x/y: esquina del cuadrilatero
    en coordenadas de superficie, para que el pixel (0,0) de salida
    corresponda a esa esquina real."""
    if salida_ancho < 16 or salida_alto < 16:
        raise ValueError("Dimensiones de salida invalidas.")
    if salida_ancho > 4096 or salida_alto > 4096:
        raise ValueError("Salida maxima 4096x4096.")
    ancho, alto, pixeles = decodificar_png_rgb(imagen_png)
    try:
        Hinv = invertir3x3(homografia)
    except ValueError as exc:
        raise SuperficieNoCalibradaError(
            "La homografia no es aplicable: " + str(exc)
        ) from exc
    salida = bytearray(bytes(FONDO) * (salida_ancho * salida_alto * 3))
    for oy in range(salida_alto):
        fila_base = oy * salida_ancho
        sy_abs = origen_y + oy + 0.5
        for ox in range(salida_ancho):
            sx, sy = aplicar(Hinv, origen_x + ox + 0.5, sy_abs)
            if 0.0 <= sx < ancho and 0.0 <= sy < alto:
                idx = (int(sy) * ancho + int(sx)) * 3
                out = (fila_base + ox) * 3
                salida[out] = pixeles[idx]
                salida[out + 1] = pixeles[idx + 1]
                salida[out + 2] = pixeles[idx + 2]
    return encode_png_rgb(
        salida_ancho, salida_alto,
        _normalizar(salida, salida_ancho * salida_alto * 3),
    )


def caja_del_cuadrilatero(corners: list) -> tuple:
    xs = [float(p[0]) for p in corners]
    ys = [float(p[1]) for p in corners]
    x0 = max(0.0, min(xs))
    y0 = max(0.0, min(ys))
    x1 = max(xs)
    y1 = max(ys)
    return (int(x0), int(y0), max(1, int(x1 - x0)), max(1, int(y1 - y0)))
