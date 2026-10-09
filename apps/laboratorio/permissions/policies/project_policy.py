"""Politica de acceso a proyectos: propietario o gobernador."""

from apps.laboratorio.permissions.rules.access_rules import (
    es_propietario,
    puede_gobernar,
)
from apps.laboratorio.shared.exceptions.domain_errors import PermisoDenegadoError


class PoliticaProyecto:
    @staticmethod
    def ver(proyecto, identidad) -> bool:
        return es_propietario(proyecto, identidad.zid) or puede_gobernar(identidad)

    @staticmethod
    def editar(proyecto, identidad) -> bool:
        return PoliticaProyecto.ver(proyecto, identidad)

    @staticmethod
    def eliminar(proyecto, identidad) -> bool:
        return PoliticaProyecto.ver(proyecto, identidad)

    @staticmethod
    def exigir_ver(proyecto, identidad) -> None:
        if not PoliticaProyecto.ver(proyecto, identidad):
            raise PermisoDenegadoError(
                "Solo el propietario o un gobernador puede acceder a este proyecto."
            )

    @staticmethod
    def exigir_editar(proyecto, identidad) -> None:
        if not PoliticaProyecto.editar(proyecto, identidad):
            raise PermisoDenegadoError(
                "Solo el propietario o un gobernador puede modificar este proyecto."
            )
