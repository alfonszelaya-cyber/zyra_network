"""Estados de un motor registrado en el registro de motores."""

from enum import Enum


class EngineStatus(str, Enum):
    """Ley 1 de LABORATORIO: un motor JAMAS finge exito.

    Si el hardware o la capacidad no existen, el motor se registra
    con estado NO_DISPONIBLE y lo reporta con honestidad total.
    """

    DISPONIBLE = "disponible"
    NO_DISPONIBLE = "no_disponible"
    EN_MANTENIMIENTO = "en_mantenimiento"
    ERROR = "error"
