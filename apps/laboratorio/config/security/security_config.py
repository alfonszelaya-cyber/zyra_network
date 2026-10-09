"""Configuracion de seguridad de LABORATORIO."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityConfig:
    """Limites de texto, firmas y modo estricto de sanitizacion."""

    largo_maximo_texto: int = 20000
    bytes_token: int = 32
    firmar_documentos: bool = True
    modo_estricto: bool = True

    @classmethod
    def cargar(cls) -> "SecurityConfig":
        """Carga desde entorno; el modo estricto no se apaga en produccion."""
        return cls(
            largo_maximo_texto=int(os.environ.get("LAB_SEC_TEXTO_MAX", cls.largo_maximo_texto)),
            bytes_token=int(os.environ.get("LAB_SEC_TOKEN", cls.bytes_token)),
            firmar_documentos=os.environ.get("LAB_SEC_FIRMAR", "1") == "1",
            modo_estricto=os.environ.get("LAB_SEC_ESTRICTO", "1") == "1",
        )
