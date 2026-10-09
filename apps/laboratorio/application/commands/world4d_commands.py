"""Comandos del 4D: tiempo, luz e interaccion."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ComandoCrearLineaTiempo:
    escena_id: str
    duracion_s: float
    fps: int
    pistas: tuple


@dataclass(frozen=True)
class ComandoCrearProgramaLuz:
    escena_id: str
    pasos: tuple
    ambientar_fondo: bool


@dataclass(frozen=True)
class ComandoCrearInteraccion:
    escena_id: str
    x: float
    y: float
    w: float
    h: float
    accion: str
    titulo: str
