"""Configuracion de prefijos de rutas HTTP de LABORATORIO."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RoutesConfig:
    """Prefijos oficiales: publico, api, interno y websocket."""

    prefijo_publico: str = "/laboratorio"
    prefijo_api: str = "/laboratorio/api"
    prefijo_interno: str = "/laboratorio/internal"
    prefijo_ws: str = "/laboratorio/ws"
    version_api: str = "v1"

    @classmethod
    def cargar(cls) -> "RoutesConfig":
        """Carga desde entorno manteniendo el nombre de app como raiz."""
        return cls(
            prefijo_publico=os.environ.get("LAB_RUTA_PUBLICA", cls.prefijo_publico),
            prefijo_api=os.environ.get("LAB_RUTA_API", cls.prefijo_api),
            prefijo_interno=os.environ.get("LAB_RUTA_INTERNA", cls.prefijo_interno),
            prefijo_ws=os.environ.get("LAB_RUTA_WS", cls.prefijo_ws),
            version_api=os.environ.get("LAB_RUTA_VERSION", cls.version_api),
        )
