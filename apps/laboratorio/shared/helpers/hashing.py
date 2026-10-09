"""Utilidades de hash SHA-256 (estandar de integridad ZYRA)."""

import hashlib


def sha256_texto(texto: str) -> str:
    """Hash SHA-256 hexadecimal de un texto UTF-8."""
    if not isinstance(texto, str):
        raise ValueError("Se esperaba texto para calcular hash.")
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def sha256_bytes(datos: bytes) -> str:
    """Hash SHA-256 hexadecimal de datos binarios."""
    if not isinstance(datos, (bytes, bytearray)):
        raise ValueError("Se esperaban bytes para calcular hash.")
    return hashlib.sha256(bytes(datos)).hexdigest()


def verificar_texto(texto: str, hash_esperado: str) -> bool:
    """Compara el hash de un texto contra un hash esperado."""
    return sha256_texto(texto) == (hash_esperado or "").lower()
