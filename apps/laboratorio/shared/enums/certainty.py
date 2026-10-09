"""Niveles de certeza para informacion procesada (estandar ZYRA)."""

from enum import Enum


class Certainty(str, Enum):
    """Toda informacion derivada declara su nivel de certeza."""

    EVIDENCIA_ENCONTRADA = "evidencia_encontrada"
    EVIDENCIA_VERIFICADA = "evidencia_verificada"
    RECONSTRUCCION = "reconstruccion"
    INFERENCIA = "inferencia"
    INCERTIDUMBRE = "incertidumbre"
