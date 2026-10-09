"""Utilidades de archivos con proteccion anti path-traversal."""
from pathlib import Path


def ruta_segura(base, *partes) -> Path:
    """Resuelve base/partes y falla si el resultado escapa de base."""
    base_resuelta = Path(base).resolve()
    if not partes:
        raise ValueError("ruta_segura requiere partes de ruta.")
    candidata = base_resuelta.joinpath(*[str(p) for p in partes]).resolve()
    if candidata != base_resuelta and base_resuelta not in candidata.parents:
        raise ValueError("Ruta fuera de la base permitida: " + candidata.name)
    return candidata


def tamano_dentro_de_limite(datos: bytes, maximo_mb: float) -> bool:
    """True si los bytes no exceden el limite en MB."""
    if not isinstance(maximo_mb, (int, float)) or maximo_mb <= 0:
        raise ValueError("maximo_mb debe ser positivo.")
    if not isinstance(datos, (bytes, bytearray)):
        raise ValueError("Se esperaban bytes.")
    return len(datos) <= int(maximo_mb * 1024 * 1024)


def extension_segura(nombre_archivo: str) -> str:
    """Devuelve la extension validada (alfanumerica) o falla."""
    if not isinstance(nombre_archivo, str) or not nombre_archivo.strip():
        raise ValueError("Nombre de archivo invalido.")
    ext = Path(nombre_archivo).suffix.lower().lstrip(".")
    if not ext or not ext.isalnum():
        raise ValueError("Extension invalida o ausente: " + repr(nombre_archivo))
    return ext
