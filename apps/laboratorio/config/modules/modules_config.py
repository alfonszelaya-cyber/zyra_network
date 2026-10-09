"""Configuracion de los 17 modulos verticales de LABORATORIO."""
import os
from dataclasses import dataclass

MODULOS_OFICIALES = (
    "capture", "understanding", "design", "creation", "world4d",
    "simulation", "testing", "comparison", "optimization", "render",
    "presentation", "projection", "display", "export", "library",
    "network", "governance",
)


@dataclass(frozen=True)
class ModulesConfig:
    """Lista cerrada de modulos activos: nunca inventados."""

    modulos_activos: tuple = MODULOS_OFICIALES
    auto_registro: bool = True

    @classmethod
    def cargar(cls) -> "ModulesConfig":
        """LAB_MODULOS permite activar un subconjunto validado."""
        texto = os.environ.get("LAB_MODULOS", "")
        if texto.strip():
            pedidos = tuple(m.strip() for m in texto.split(",") if m.strip())
            for m in pedidos:
                if m not in MODULOS_OFICIALES:
                    raise ValueError("Modulo desconocido: " + m)
            return cls(modulos_activos=pedidos)
        return cls()
