"""Errores del sistema de render."""

from apps.laboratorio.shared.exceptions.base import LaboratorioError


class RenderFallidoError(LaboratorioError):
    """El trabajo de render termino en error real."""

    codigo = "render_fallido"


class CalidadNoSoportadaError(LaboratorioError):
    """La calidad pedida no esta soportada por el motor."""

    codigo = "calidad_no_soportada"


class EscenaVaciaError(LaboratorioError):
    """Se pidio render de una escena sin objetos."""

    codigo = "escena_vacia"


class MotorNoDisponibleError(LaboratorioError):
    """El motor requerido esta registrado como no disponible."""

    codigo = "motor_no_disponible"
