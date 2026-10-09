"""Errores de comunicacion con ZYRA Network."""

from apps.laboratorio.shared.exceptions.base import LaboratorioError


class RedNoDisponibleError(LaboratorioError):
    """ZYRA Core no responde."""

    codigo = "red_no_disponible"


class RegistroFallidoError(LaboratorioError):
    """El registro de la app en la red fallo."""

    codigo = "registro_fallido"


class SelladoFallidoError(LaboratorioError):
    """El sellado de un documento fallo."""

    codigo = "sellado_fallido"


class RespuestaInvalidaError(LaboratorioError):
    """La respuesta de la red no cumple el contrato."""

    codigo = "respuesta_invalida"
