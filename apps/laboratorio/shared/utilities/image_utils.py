"""Deteccion de formatos de imagen por firma y dimensiones PNG."""
import struct

FIRMA_PNG = b"\x89PNG\r\n\x1a\n"
FIRMA_JPEG = b"\xff\xd8\xff"


def detectar_formato(datos: bytes) -> str:
    """Devuelve 'png', 'jpeg' o 'desconocido' segun la firma real."""
    if not isinstance(datos, (bytes, bytearray)) or not datos:
        raise ValueError("Se requieren bytes para detectar formato.")
    if bytes(datos[:8]) == FIRMA_PNG:
        return "png"
    if bytes(datos[:3]) == FIRMA_JPEG:
        return "jpeg"
    return "desconocido"


def dimensiones_png(datos: bytes) -> tuple:
    """Extrae (ancho, alto) de la cabecera IHDR de un PNG."""
    if detectar_formato(datos) != "png":
        raise ValueError("Los datos no son un PNG.")
    if len(datos) < 24:
        raise ValueError("PNG truncado: faltan bytes de cabecera.")
    ancho, alto = struct.unpack(">II", bytes(datos[16:24]))
    return (int(ancho), int(alto))


def es_imagen_valida(datos: bytes) -> bool:
    """True solo si los bytes son PNG o JPEG reales."""
    return detectar_formato(datos) in ("png", "jpeg")
