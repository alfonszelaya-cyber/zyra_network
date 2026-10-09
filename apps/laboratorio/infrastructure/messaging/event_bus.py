"""Bus de eventos en memoria (implementa el puerto EventBus)."""

from apps.laboratorio.shared.interfaces.event_bus import (
    EventBus,
    Evento,
    ManejadorEvento,
)
from apps.laboratorio.shared.utilities.logging_utils import obtener_logger


class BusEventos(EventBus):
    """Publica a suscriptores aislando errores de manejadores."""

    def __init__(self):
        self._suscriptores = {}
        self._logger = obtener_logger("bus_eventos")

    def suscribir(self, nombre_evento: str, manejador: ManejadorEvento) -> None:
        if not nombre_evento or not callable(manejador):
            raise ValueError("Suscripcion requiere nombre y manejador callable.")
        self._suscriptores.setdefault(nombre_evento, []).append(manejador)

    def publicar(self, evento: Evento) -> int:
        if not isinstance(evento, Evento):
            raise ValueError("publicar requiere un Evento.")
        entregados = 0
        for manejador in self._suscriptores.get(evento.nombre, ()):
            try:
                manejador(evento)
                entregados += 1
            except Exception as exc:
                self._logger.error(
                    "manejador fallo para " + evento.nombre + ": "
                    + type(exc).__name__ + ": " + str(exc)
                )
        return entregados
