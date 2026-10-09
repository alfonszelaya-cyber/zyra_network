"""Fabrica de Proyectos: unica via de creacion validada."""
from apps.laboratorio.domain.project import Proyecto
from apps.laboratorio.shared.enums.creation_type import CreationType
from apps.laboratorio.shared.models.identifiers import nuevo_id


class ProyectoFactory:
    """Crea proyectos con id nuevo y tipo oficial validado."""

    @staticmethod
    def crear(
        titulo: str,
        descripcion: str,
        tipo_creacion,
        propietario_zid: str,
        etiquetas=None,
    ) -> Proyecto:
        if isinstance(tipo_creacion, str):
            tipo = CreationType.validar(tipo_creacion)
        elif isinstance(tipo_creacion, CreationType):
            tipo = tipo_creacion
        else:
            raise ValueError("tipo_creacion invalido.")
        return Proyecto(
            id=nuevo_id("proy"),
            titulo=titulo,
            descripcion=descripcion or "",
            tipo_creacion=tipo,
            propietario_zid=propietario_zid,
            etiquetas=list(etiquetas or []),
        )
