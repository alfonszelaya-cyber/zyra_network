"""Configuracion de los registros (menus, rutas, motores, roles)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RegistryConfig:
    """Comportamiento del registro de la aplicacion."""

    auto_registro: bool = True
    validar_unicidad: bool = True
    exigir_manifest: bool = True

    @classmethod
    def cargar(cls) -> "RegistryConfig":
        """Carga desde entorno con valores estrictos por defecto."""
        return cls(
            auto_registro=os.environ.get("LAB_REG_AUTO", "1") == "1",
            validar_unicidad=os.environ.get("LAB_REG_UNICO", "1") == "1",
            exigir_manifest=os.environ.get("LAB_REG_MANIFEST", "1") == "1",
        )
