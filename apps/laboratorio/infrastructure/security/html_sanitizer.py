"""Escapado HTML obligatorio para todo dato mostrado o incrustado."""

import html


def escapar(texto) -> str:
    """Escapa un valor individual para HTML seguro."""
    return html.escape(str(texto), quote=True)


def escapar_estructura(datos):
    """Escapa recursivamente dict/list conservando tipos numericos."""
    if isinstance(datos, dict):
        return {str(escapar(k)): escapar_estructura(v) for k, v in datos.items()}
    if isinstance(datos, (list, tuple)):
        return [escapar_estructura(v) for v in datos]
    if isinstance(datos, str):
        return escapar(datos)
    return datos
