"""Configuracion de red hacia ZYRA Core.

Sin URL configurada el cliente se niega a llamar (Ley 1: honestidad).
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkConfig:
    """Parametros de conexion con la red ZYRA."""

    url_zyra_core: str = ""
    app_id: str = "laboratorio"
    api_token: str = ""
    timeout_segundos: float = 30.0
    reintentos: int = 3

    @property
    def configurada(self) -> bool:
        """True solo si existe URL real de ZYRA Core."""
        return bool(self.url_zyra_core.strip())

    @classmethod
    def cargar(cls) -> "NetworkConfig":
        """LAB_ZYRA_URL es obligatoria en despliegue real."""
        return cls(
            url_zyra_core=os.environ.get("LAB_ZYRA_URL", ""),
            app_id=os.environ.get("LAB_ID_APP", cls.app_id),
            api_token=os.environ.get("LAB_ZYRA_TOKEN", ""),
            timeout_segundos=float(os.environ.get("LAB_NET_TIMEOUT", cls.timeout_segundos)),
            reintentos=int(os.environ.get("LAB_NET_REINTENTOS", cls.reintentos)),
        )
