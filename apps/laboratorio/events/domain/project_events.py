"""Eventos de dominio del agregado Proyecto."""

from apps.laboratorio.constants.events.event_names import EventoNombre
from apps.laboratorio.shared.interfaces.event_bus import Evento


def proyecto_creado(proyecto_id: str, titulo: str, autor_zid: str) -> Evento:
    return Evento(
        nombre=EventoNombre.PROYECTO_CREADO,
        datos={
            "proyecto_id": proyecto_id,
            "titulo": titulo,
            "autor_zid": autor_zid,
        },
    )
