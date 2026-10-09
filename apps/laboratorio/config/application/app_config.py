"""Configuracion general de la aplicacion LABORATORIO."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """Identidad y modo de operacion de la app."""

    nombre_app: str = "ZYRA LABORATORIO"
    id_app: str = "laboratorio"
    version: str = "0.1.0"
    debug: bool = False
    idioma: str = "es"

    @classmethod
    def cargar(cls) -> "AppConfig":
        """Carga desde variables de entorno LAB_* con valores seguros."""
        return cls(
            nombre_app=os.environ.get("LAB_NOMBRE_APP", cls.nombre_app),
            id_app=os.environ.get("LAB_ID_APP", cls.id_app),
            version=os.environ.get("LAB_VERSION", cls.version),
            debug=os.environ.get("LAB_DEBUG", "0") == "1",
            idioma=os.environ.get("LAB_IDIOMA", cls.idioma),
        )
