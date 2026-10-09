"""Configuracion de control de acceso de LABORATORIO."""
import os
from dataclasses import dataclass

from apps.laboratorio.constants.roles.role_codes import RolCodigo


@dataclass(frozen=True)
class PermissionsConfig:
    """Politica de acceso por defecto de la aplicacion."""

    rol_defecto: str = RolCodigo.ESPECTADOR
    exigir_zid: bool = True
    sanear_entrada: bool = True

    @classmethod
    def cargar(cls) -> "PermissionsConfig":
        """Carga desde entorno; rol desconocido se rechaza."""
        rol = os.environ.get("LAB_ROL_DEFECTO", cls.rol_defecto)
        if rol not in RolCodigo.TODOS:
            raise ValueError("Rol por defecto desconocido: " + rol)
        return cls(
            rol_defecto=rol,
            exigir_zid=os.environ.get("LAB_EXIGIR_ZID", "1") == "1",
            sanear_entrada=os.environ.get("LAB_SANEAR", "1") == "1",
        )
