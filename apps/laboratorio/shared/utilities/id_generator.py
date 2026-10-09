"""Generadores de ids legibles y codigos cortos.

Diferencia con models.identifiers (dueño de Identificador de dominio):
aqui se producen slugs y codigos de presentacion, no entidades.
"""
import re
import secrets
import time
import unicodedata


def slug(texto: str, maximo: int = 40) -> str:
    """Convierte texto a slug ascii: 'ZYRA El Salvador' -> 'zyra-el-salvador'."""
    if not isinstance(texto, str):
        raise ValueError("slug requiere texto.")
    normalizado = unicodedata.normalize("NFKD", texto)
    ascii_puro = normalizado.encode("ascii", "ignore").decode("ascii")
    limpio = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_puro).strip("-").lower()
    if not limpio:
        limpio = "sin-nombre"
    return limpio[:maximo].strip("-")


def id_legible(prefijo: str, texto: str = "") -> str:
    """Produce ids tipo 'proy-zyra-el-salvador-a1b2c3'."""
    if not prefijo or not prefijo.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Prefijo invalido: " + repr(prefijo))
    partes = [prefijo]
    if texto.strip():
        partes.append(slug(texto))
    partes.append(secrets.token_hex(3))
    return "-".join(partes)


def codigo_corto(longitud_bytes: int = 4) -> str:
    """Codigo hex aleatorio corto para verificacion visual."""
    if not 1 <= longitud_bytes <= 32:
        raise ValueError("longitud_bytes debe estar entre 1 y 32.")
    return secrets.token_hex(longitud_bytes)


def marca_tiempo_compacta() -> str:
    """Milisegundos epoch en hex, para ordenar sin ambiguedad."""
    return format(int(time.time() * 1000), "x")
