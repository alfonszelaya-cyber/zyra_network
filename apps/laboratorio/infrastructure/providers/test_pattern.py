"""Patron de prueba real para destinos de salida."""
from apps.laboratorio.infrastructure.providers.png_encoder import encode_png_rgb

BARRAS = (
    (229, 57, 53), (240, 196, 32), (67, 160, 71),
    (30, 99, 235), (245, 245, 245),
)


def patron_prueba(ancho: int, alto: int) -> bytes:
    """Genera un PNG de barras de color con rejilla blanca."""
    if ancho < 16 or alto < 16:
        raise ValueError("Dimensiones del patron invalidas.")
    if ancho > 2048 or alto > 2048:
        raise ValueError("El patron maximo es 2048x2048.")
    filas = bytearray()
    for y in range(alto):
        for x in range(ancho):
            banda = min(len(BARRAS) - 1, x * len(BARRAS) // ancho)
            r, g, b = BARRAS[banda]
            if x % 40 < 2 or y % 40 < 2:
                r, g, b = 255, 255, 255
            filas += bytes((r, g, b))
    return encode_png_rgb(ancho, alto, bytes(filas))
