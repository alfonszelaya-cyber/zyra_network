"""Validacion central de nombres de eventos (viven en constants)."""

from apps.laboratorio.constants.events.event_names import EventoNombre


def nombres_oficiales() -> tuple:
    return tuple(
        v for k, v in vars(EventoNombre).items()
        if k.isupper() and isinstance(v, str)
    )


def es_oficial(nombre: str) -> bool:
    return nombre in nombres_oficiales()


def validar_nombre(nombre: str) -> str:
    if not es_oficial(nombre):
        raise ValueError("Evento no oficial: " + repr(nombre))
    return nombre
