"""Validaciones comunes de la capa HTTP."""
import json

MAXIMO_CUERPO_BYTES = 1048576


def validar_cuerpo_json(cuerpo_bytes, maximo_bytes: int = MAXIMO_CUERPO_BYTES) -> dict:
    if cuerpo_bytes in (None, b""):
        raise ValueError("Cuerpo de la peticion vacio.")
    if not isinstance(cuerpo_bytes, (bytes, bytearray)):
        raise ValueError("Cuerpo invalido.")
    if len(cuerpo_bytes) > maximo_bytes:
        raise ValueError("Cuerpo excede el maximo de bytes permitido.")
    try:
        datos = json.loads(bytes(cuerpo_bytes).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Cuerpo no es JSON valido.") from exc
    if not isinstance(datos, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON.")
    return datos


def validar_paginacion(query: dict) -> tuple:
    def _entero(nombre, defecto):
        crudo = query.get(nombre)
        if crudo is None:
            return defecto
        try:
            return int(str(crudo))
        except ValueError as exc:
            raise ValueError(nombre + " debe ser entero.") from exc

    pagina = _entero("pagina", 1)
    por_pagina = _entero("por_pagina", 20)
    if pagina < 1:
        raise ValueError("pagina debe ser mayor o igual a 1.")
    if not 1 <= por_pagina <= 100:
        raise ValueError("por_pagina debe estar entre 1 y 100.")
    return pagina, por_pagina


def validar_etiquetas(valor) -> tuple:
    if valor is None:
        return ()
    if not isinstance(valor, list):
        raise ValueError("etiquetas debe ser una lista.")
    limpias = []
    for item in valor:
        if not isinstance(item, str):
            raise ValueError("Cada etiqueta debe ser texto.")
        limpia = item.strip().lower()
        if limpia and limpia not in limpias and len(limpia) <= 40:
            limpias.append(limpia)
    return tuple(limpias)
