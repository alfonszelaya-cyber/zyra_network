"""Configuracion del bus de eventos y outbox."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EventsConfig:
    """Parametros de eventos y reintentos hacia la red."""

    bus_en_memoria: bool = True
    outbox_habilitado: bool = True
    reintentos: int = 3
    espera_reintento_segundos: float = 5.0

    @classmethod
    def cargar(cls) -> "EventsConfig":
        """Carga desde entorno con limites de produccion."""
        return cls(
            bus_en_memoria=os.environ.get("LAB_EVENTOS_MEMORIA", "1") == "1",
            outbox_habilitado=os.environ.get("LAB_OUTBOX", "1") == "1",
            reintentos=int(os.environ.get("LAB_EVENTOS_REINTENTOS", cls.reintentos)),
            espera_reintento_segundos=float(
                os.environ.get("LAB_EVENTOS_ESPERA", cls.espera_reintento_segundos)
            ),
        )
