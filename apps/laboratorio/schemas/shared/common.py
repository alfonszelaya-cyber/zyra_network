"""Constantes y codigos comunes del contrato HTTP."""

MIME_JSON = "application/json; charset=utf-8"
MIME_SVG = "image/svg+xml"

CODIGOS_ERROR = {
    "cuerpo_invalido": 400,
    "valor_invalido": 400,
    "zid_ausente": 401,
    "permiso_denegado": 403,
    "entidad_no_encontrada": 404,
    "estado_invalido": 409,
    "error_interno": 500,
}


def status_para(codigo_error: str) -> int:
    return CODIGOS_ERROR.get(codigo_error, 500)
