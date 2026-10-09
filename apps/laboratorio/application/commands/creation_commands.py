"""Comandos de creacion y biblioteca."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ComandoCrearEscena:
    proyecto_id: str
    nombre: str
    ancho: int
    alto: int
    objetos: tuple


@dataclass(frozen=True)
class ComandoGenerarArtefacto:
    escena_id: str
    formato: str


@dataclass(frozen=True)
class ComandoCrearActivo:
    nombre: str
    tipo: str
    contenido: str
    etiquetas: tuple
