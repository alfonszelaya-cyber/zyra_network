"""Puerto del bus de eventos de dominio."""
import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from apps.laboratorio.shared.types.json_type import ObjetoJSON


@dataclass(frozen=True)
class Evento:
    """Hecho de dominio publicado en el bus."""

    nombre: str
    datos: ObjetoJSON = field(default_factory=dict)
    ocurrido_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


ManejadorEvento = Callable[[Evento], None]


class EventBus(abc.ABC):
    """Contrato de publicacion/suscripcion de eventos."""

    @abc.abstractmethod
    def publicar(self, evento: Evento) -> None:
        """Publica un evento a todos sus suscriptores."""

    @abc.abstractmethod
    def suscribir(self, nombre_evento: str, manejador: ManejadorEvento) -> None:
        """Registra un manejador para un nombre de evento."""
