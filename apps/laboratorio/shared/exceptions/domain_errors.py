"""Errores de reglas de negocio del dominio."""

from apps.laboratorio.shared.exceptions.base import LaboratorioError


class EntidadNoEncontradaError(LaboratorioError):
    """La entidad solicitada no existe."""

    codigo = "entidad_no_encontrada"


class EstadoInvalidoError(LaboratorioError):
    """El estado actual no permite la operacion."""

    codigo = "estado_invalido"


class ValorInvalidoError(LaboratorioError):
    """Un valor de dominio viola sus reglas."""

    codigo = "valor_invalido"


class PermisoDenegadoError(LaboratorioError):
    """El usuario no tiene permiso para la operacion."""

    codigo = "permiso_denegado"
