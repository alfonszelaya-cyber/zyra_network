"""Configuracion del sistema: entorno, limites e idioma."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SystemConfig:
    """Parametros globales de operacion."""

    entorno: str = "produccion"
    zona_horaria: str = "UTC"
    max_import_mb: float = 512.0
    idioma: str = "es"
    pais: str = "SV"

    @classmethod
    def cargar(cls) -> "SystemConfig":
        """Carga desde entorno; produccion es el valor por defecto."""
        return cls(
            entorno=os.environ.get("LAB_ENTORNO", cls.entorno),
            zona_horaria=os.environ.get("LAB_ZONA", cls.zona_horaria),
            max_import_mb=float(os.environ.get("LAB_MAX_IMPORT_MB", cls.max_import_mb)),
            idioma=os.environ.get("LAB_IDIOMA", cls.idioma),
            pais=os.environ.get("LAB_PAIS", cls.pais),
        )
