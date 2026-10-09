"""Sobre oficial de respuestas: ok con datos, o error tipificado."""

from apps.laboratorio.schemas.shared.common import status_para
from apps.laboratorio.shared.exceptions.base import LaboratorioError


def exito(datos: dict = None, status: int = 200) -> tuple:
    return status, {"ok": True, "datos": dict(datos or {}), "error": {}}


def error(codigo: str, mensaje: str, status: int = None) -> tuple:
    estado = status or status_para(codigo)
    return estado, {
        "ok": False,
        "datos": {},
        "error": {"codigo": codigo, "mensaje": mensaje},
    }


def desde_excepcion(exc: Exception) -> tuple:
    if isinstance(exc, LaboratorioError):
        return error(exc.codigo, exc.mensaje)
    if isinstance(exc, ValueError):
        return error("valor_invalido", str(exc))
    return error("error_interno", "Error interno de la aplicacion.")
