"""Esquema de creacion de proyecto (borde HTTP)."""

from apps.laboratorio.shared.enums.creation_type import CreationType
from apps.laboratorio.validators.shared.common_validators import validar_etiquetas


class SchemaCrearProyecto:
    MAX_TITULO = 200
    MAX_DESCRIPCION = 2000

    @classmethod
    def validar(cls, datos) -> dict:
        if not isinstance(datos, dict):
            raise ValueError("Cuerpo de proyecto invalido.")
        titulo = str(datos.get("titulo", "")).strip()
        if not titulo:
            raise ValueError("El proyecto requiere titulo.")
        if len(titulo) > cls.MAX_TITULO:
            raise ValueError("Titulo excede " + str(cls.MAX_TITULO) + " caracteres.")
        descripcion = str(datos.get("descripcion", "")).strip()
        if len(descripcion) > cls.MAX_DESCRIPCION:
            raise ValueError("Descripcion excede el maximo permitido.")
        tipo = CreationType.validar(str(datos.get("tipo", ""))).value
        etiquetas = list(validar_etiquetas(datos.get("etiquetas")))
        return {
            "titulo": titulo,
            "descripcion": descripcion,
            "tipo": tipo,
            "etiquetas": etiquetas,
        }
