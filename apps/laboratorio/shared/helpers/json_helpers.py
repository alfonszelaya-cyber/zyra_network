"""Utilidades JSON seguras para persistencia y API."""

import json
from typing import Any

from apps.laboratorio.shared.types.json_type import ObjetoJSON


def a_json(objeto: Any, ordenado: bool = True) -> str:
    """Serializa a texto JSON seguro."""
    return json.dumps(objeto, ensure_ascii=True, sort_keys=ordenado, default=str)


def desde_json(texto: str) -> ObjetoJSON:
    """Deserializa un texto JSON y exige que sea un objeto."""
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("Texto JSON vacio o invalido.")
    datos = json.loads(texto)
    if not isinstance(datos, dict):
        raise ValueError("El JSON debe representar un objeto {clave: valor}.")
    return datos


def intentar_desde_json(texto: str) -> ObjetoJSON:
    """Deserializa o devuelve dict vacio si es invalido."""
    try:
        return desde_json(texto)
    except ValueError:
        return {}
