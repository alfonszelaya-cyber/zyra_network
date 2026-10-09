"""Suscripciones que envian eventos de dominio a ZYRA Core via outbox."""

from apps.laboratorio.constants.events.event_names import EventoNombre
from apps.laboratorio.infrastructure.network.zyra_client import DESTINO_SELLO
from apps.laboratorio.shared.helpers.json_helpers import a_json


class SuscriptorZyra:
    """Conecta bus -> outbox: todo evento relevante se sella en ZYRA."""

    def __init__(self, bus, outbox):
        if bus is None or outbox is None:
            raise ValueError("SuscriptorZyra requiere bus y outbox.")
        self._bus = bus
        self._outbox = outbox

    def conectar(self) -> int:
        self._bus.suscribir(EventoNombre.PROYECTO_CREADO, self._encolar_sello)
        self._bus.suscribir(EventoNombre.ESCENARIO_EVALUADO, self._encolar_sello)
        return 2

    def _encolar_sello(self, evento) -> None:
        datos = dict(evento.datos)
        titulo = str(datos.get("titulo") or "LABORATORIO/" + evento.nombre)
        self._outbox.encolar(evento.nombre, DESTINO_SELLO, {"titulo": titulo, "contenido": a_json(datos)})
