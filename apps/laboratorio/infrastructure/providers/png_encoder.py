"""Encoder PNG real con stdlib (struct + zlib).

Produce PNGs validos sin dependencias externas. Verificable con
shared/utilities/image_utils (firma y dimensiones IHDR).
"""
import struct
import zlib

FIRMA = b"\x89PNG\r\n\x1a\n"


def _chunk(tipo: bytes, datos: bytes) -> bytes:
    """Chunk PNG: longitud + tipo + datos + CRC32."""
    if len(tipo) != 4:
        raise ValueError("Tipo de chunk debe tener 4 bytes.")
    return (
        struct.pack(">I", len(datos)) + tipo + datos
        + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)
    )


def encode_png_rgb(ancho: int, alto: int, pixeles: bytes) -> bytes:
    """Codifica un buffer RGB de 8 bits (3 bytes por pixel) a PNG."""
    if ancho < 1 or alto < 1:
        raise ValueError("Dimensiones del PNG invalidas.")
    esperado = ancho * alto * 3
    if not isinstance(pixeles, (bytes, bytearray)) or len(pixeles) != esperado:
        raise ValueError(
            "El buffer RGB debe tener " + str(esperado) + " bytes."
        )
    ihdr = struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0)
    filas = bytearray()
    paso = ancho * 3
    for y in range(alto):
        filas.append(0)
        filas += pixeles[y * paso:(y + 1) * paso]
    idat = zlib.compress(bytes(filas), 6)
    return (
        FIRMA + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")
    )


def encode_png_gray(ancho: int, alto: int, pixeles: bytes) -> bytes:
    """Codifica un buffer de escala de grises de 8 bits a PNG."""
    if ancho < 1 or alto < 1:
        raise ValueError("Dimensiones del PNG invalidas.")
    esperado = ancho * alto
    if not isinstance(pixeles, (bytes, bytearray)) or len(pixeles) != esperado:
        raise ValueError(
            "El buffer de grises debe tener " + str(esperado) + " bytes."
        )
    ihdr = struct.pack(">IIBBBBB", ancho, alto, 8, 0, 0, 0, 0)
    filas = bytearray()
    for y in range(alto):
        filas.append(0)
        filas += pixeles[y * ancho:(y + 1) * ancho]
    idat = zlib.compress(bytes(filas), 6)
    return (
        FIRMA + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")
    )
