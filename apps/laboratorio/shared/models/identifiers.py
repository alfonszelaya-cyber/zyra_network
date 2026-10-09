"""Identificadores unicos con prefijo por entidad."""

import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class Identificador:
    """ID inmutable con prefijo de entidad y sufijo aleatorio."""

    prefijo: str
    valor: str

    def __post_init__(self):
        if not self.prefijo or not self.prefijo.replace("_", "").isalnum():
            raise ValueError(
                "Prefijo de identificador invalido: " + repr(self.prefijo)
            )
        if not self.valor:
            raise ValueError("El identificador requiere un valor.")

    def __str__(self) -> str:
        return self.prefijo + "_" + self.valor


def nuevo_id(prefijo: str) -> Identificador:
    """Genera un identificador nuevo: prefijo_ + 16 hex aleatorios."""
    return Identificador(prefijo=prefijo, valor=secrets.token_hex(8))


def id_desde_texto(prefijo: str, texto: str) -> Identificador:
    """Valida y convierte texto 'prefijo_valor' a Identificador."""
    esperado = prefijo + "_"
    if not isinstance(texto, str) or not texto.startswith(esperado):
        raise ValueError(
            "Identificador invalido para '" + prefijo + "': " + repr(texto)
        )
    valor = texto[len(esperado):]
    if not valor:
        raise ValueError("Identificador sin valor: " + repr(texto))
    return Identificador(prefijo=prefijo, valor=valor)
