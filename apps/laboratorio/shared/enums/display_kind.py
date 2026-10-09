"""Destinos de salida de la Display Abstraction."""

from enum import Enum


class DisplayKind(str, Enum):
    """El mismo contenido puede salir por cualquiera de estos destinos.

    La arquitectura es invertida: primero el mundo (SCENE/WORLD),
    despues el render, y al final el destino de salida sustituible.
    """

    PANTALLA = "pantalla"
    PROYECTOR = "proyector"
    HOLOGRAFICO = "holografico"
    LIGHT_FIELD = "light_field"
    AR = "ar"
    VR = "vr"
    FUTURO = "futuro"
