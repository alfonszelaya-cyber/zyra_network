"""Eventos de dominio de escenarios A/B/C."""

from apps.laboratorio.constants.events.event_names import EventoNombre
from apps.laboratorio.shared.interfaces.event_bus import Evento


def escenario_evaluado(
    escenario_id: str, proyecto_id: str, tipo: str, puntaje: float, autor_zid: str
) -> Evento:
    return Evento(
        nombre=EventoNombre.ESCENARIO_EVALUADO,
        datos={
            "escenario_id": escenario_id,
            "proyecto_id": proyecto_id,
            "tipo": tipo,
            "puntaje_total": puntaje,
            "autor_zid": autor_zid,
        },
    )
