"""Configuracion de red hacia ZYRA Network (el nucleo vivo en main.py).

Orden automatico de deteccion de la Red:
  1. LAB_ZYRA_URL  (override explicito de laboratorio)
  2. ZYRA_URL      (la misma variable que usa la SuperApp)
  3. ZYRA_HOST     (servicio de render.yaml -> https://host)
Sin ninguna de las tres, la app funciona local y lo declara.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkConfig:
    """Parametros de conexion con ZYRA Network."""

    url_zyra_core: str = ""
    app_id: str = "laboratorio"
    api_token: str = ""
    timeout_segundos: float = 30.0
    reintentos: int = 3

    NOMBRE_RED = "ZYRA Network"

    @property
    def configurada(self) -> bool:
        """True solo si existe URL real de ZYRA Network."""
        return bool(self.url_zyra_core.strip())

    @classmethod
    def cargar(cls) -> "NetworkConfig":
        """Detecta la Red viva automaticamente (mismo contrato que superapp)."""
        url = os.environ.get("LAB_ZYRA_URL", "").strip()
        if not url:
            url = os.environ.get("ZYRA_URL", "").strip()
        if not url:
            host = os.environ.get("ZYRA_HOST", "").strip()
            if host:
                url = "https://" + host
        token = (
            os.environ.get("LAB_ZYRA_TOKEN", "").strip()
            or os.environ.get("ZYRA_API_TOKEN", "").strip()
        )
        return cls(
            url_zyra_core=url.rstrip("/"),
            app_id=os.environ.get("LAB_ID_APP", "laboratorio"),
            api_token=token,
            timeout_segundos=float(
                os.environ.get("LAB_NET_TIMEOUT", "30.0")
            ),
            reintentos=int(os.environ.get("LAB_NET_REINTENTOS", "3")),
        )
