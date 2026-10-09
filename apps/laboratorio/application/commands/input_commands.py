"""Comandos de captura, comprension y diseno."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ComandoCapturarEntrada:
    proyecto_id: str
    tipo: str
    titulo: str
    contenido: str


@dataclass(frozen=True)
class ComandoComprenderEntrada:
    entrada_id: str


@dataclass(frozen=True)
class ComandoCrearBlueprint:
    proyecto_id: str
    nombre: str
    tipo: str
    componentes: tuple
