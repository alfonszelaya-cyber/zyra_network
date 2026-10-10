"""Decodificador PNG para formatos producidos por LABORATORIO."""
import struct
import zlib

FIRMA = b"\x89PNG\r\n\x1a\n"


def decodificar_png_rgb(datos: bytes) -> tuple:
    """Devuelve (ancho, alto, pixeles_rgb) de PNG RGB 8 bits filtro 0."""
    if not isinstance(datos, (bytes, bytearray)) or bytes(datos[:8]) != FIRMA:
        raise ValueError("No es un PNG valido.")
    crudo = bytes(datos[8:])
    pos = 0
    ancho = alto = None
    idat = bytearray()
    while pos + 8 <= len(crudo):
        largo = struct.unpack(">I", crudo[pos:pos + 4])[0]
        tipo = crudo[pos + 4:pos + 8]
        cuerpo = crudo[pos + 8:pos + 8 + largo]
        if tipo == b"IHDR":
            if largo != 13:
                raise ValueError("IHDR invalido.")
            ancho, alto, profundidad, color_tipo = struct.unpack(
                ">IIBB", cuerpo[:10]
            )
            if profundidad != 8 or color_tipo != 2:
                raise ValueError(
                    "Solo se decodifican PNG RGB de 8 bits producidos "
                    "por LABORATORIO."
                )
        elif tipo == b"IDAT":
            idat += cuerpo
        elif tipo == b"IEND":
            break
        pos += 12 + largo
    if ancho is None or not idat:
        raise ValueError("PNG incompleto: faltan IHDR o IDAT.")
    inflado = zlib.decompress(bytes(idat))
    paso = ancho * 3
    if len(inflado) != (paso + 1) * alto:
        raise ValueError("Datos de imagen corruptos.")
    pixeles = bytearray(ancho * alto * 3)
    for y in range(alto):
        base = y * (paso + 1)
        if inflado[base] != 0:
            raise ValueError("Filtro PNG no soportado.")
        fila = inflado[base + 1:base + 1 + paso]
        pixeles[y * paso:(y + 1) * paso] = fila
    return ancho, alto, bytes(pixeles)
