"""Mixin de serializacion a diccionario JSON."""

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum

from apps.laboratorio.shared.models.identifiers import Identificador


def _valor_serializable(valor):
    """Convierte un valor cualquiera a algo serializable por JSON."""
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Identificador):
        return str(valor)
    if is_dataclass(valor) and not isinstance(valor, type):
        if hasattr(valor, "to_dict"):
            return valor.to_dict()
        return asdict(valor)
    if isinstance(valor, dict):
        return {str(k): _valor_serializable(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_valor_serializable(v) for v in valor]
    return valor


class SerializableMixin:
    """Convierte dataclasses a dict listo para JSON."""

    def to_dict(self) -> dict:
        """Serializa la entidad a diccionario."""
        if not is_dataclass(self):
            raise TypeError("SerializableMixin requiere una dataclass.")
        return {k: _valor_serializable(v) for k, v in asdict(self).items()}
