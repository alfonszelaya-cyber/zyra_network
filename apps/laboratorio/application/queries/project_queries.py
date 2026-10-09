"""Consultas de proyectos."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsultaListarProyectos:
    propietario_zid: str
    pagina: int = 1
    por_pagina: int = 20
