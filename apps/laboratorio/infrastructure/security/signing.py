"""Firmas HMAC-SHA256 para documentos y enlaces (integridad)."""
import hashlib
import hmac
from datetime import datetime, timezone

ALGORITMO = "hmac-sha256"


class Firmador:
    """Firma y verifica contenido con clave de la aplicacion."""

    def __init__(self, clave: str):
        if not isinstance(clave, str) or len(clave.strip()) < 16:
            raise ValueError("La clave de firma requiere al menos 16 caracteres.")
        self._clave = clave.strip().encode("utf-8")

    def firmar_texto(self, contenido: str) -> str:
        if not isinstance(contenido, str):
            raise ValueError("Contenido a firmar debe ser texto.")
        return hmac.new(
            self._clave, contenido.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def verificar(self, contenido: str, firma: str) -> bool:
        if not isinstance(firma, str) or not firma:
            return False
        return hmac.compare_digest(self.firmar_texto(contenido), firma.lower())

    def firmar_documento(self, id_documento: str, contenido: str) -> dict:
        """Produce el bloque de firma para un documento."""
        if not id_documento or not isinstance(id_documento, str):
            raise ValueError("id_documento invalido.")
        firma = self.firmar_texto(id_documento + "\n" + contenido)
        return {
            "documento_id": id_documento,
            "algoritmo": ALGORITMO,
            "firma": firma,
            "sellado_en": datetime.now(timezone.utc).isoformat(),
        }
