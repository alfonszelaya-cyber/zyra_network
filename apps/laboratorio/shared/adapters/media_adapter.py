"""Validacion de cargas media: tamano y hash de integridad."""
from apps.laboratorio.shared.helpers.hashing import sha256_bytes


class AdaptadorMedia:
    """Puerta de entrada de media: valida y sella con SHA-256."""

    LIMITE_MB_DEFECTO = 512.0

    @staticmethod
    def validar_carga(datos: bytes, maximo_mb: float = LIMITE_MB_DEFECTO) -> dict:
        """Valida bytes no vacios dentro del limite y devuelve hash."""
        if not isinstance(datos, (bytes, bytearray)) or not datos:
            raise ValueError("Carga media vacia o invalida.")
        if not isinstance(maximo_mb, (int, float)) or maximo_mb <= 0:
            raise ValueError("maximo_mb debe ser positivo.")
        if len(datos) > int(maximo_mb * 1024 * 1024):
            raise ValueError("La carga excede el limite de " + str(maximo_mb) + " MB.")
        return {"bytes": len(datos), "hash": sha256_bytes(bytes(datos))}
