"""Caso de uso: crear proyecto desde cualquier documento pegado.

Reusa CasoCrearProyecto (cero duplicacion): parsea el documento,
permite titulo/tipo manual como override, y agrega evidencia del
parseo al resultado.
"""

from apps.laboratorio.application.commands.project_commands import (
    ComandoCrearProyecto,
)
from apps.laboratorio.application.services.document_parser import (
    parsear_documento,
)
from apps.laboratorio.shared.enums.creation_type import CreationType


class CasoCrearProyectoDesdeDocumento:
    def __init__(self, caso_crear):
        if caso_crear is None:
            raise ValueError("Requiere el caso de creacion de proyectos.")
        self._caso_crear = caso_crear

    def ejecutar(self, identidad, texto_documento: str, titulo: str = None, tipo: str = None) -> dict:
        parseo = parsear_documento(texto_documento)
        titulo_final = parseo["titulo"]
        if titulo is not None:
            if not isinstance(titulo, str) or not titulo.strip():
                raise ValueError("El titulo manual no puede estar vacio.")
            titulo_final = titulo.strip()[:200]
        if tipo is not None:
            tipo_final = CreationType.validar(tipo).value
        else:
            tipo_final = parseo["tipo"]
        comando = ComandoCrearProyecto(
            titulo=titulo_final,
            descripcion=parseo["descripcion"],
            tipo=tipo_final,
            etiquetas=("documento",),
            propietario_zid=identidad.zid,
        )
        resultado = self._caso_crear.ejecutar(comando, identidad)
        resultado["documento"] = {
            "palabras": parseo["palabras"],
            "lineas": parseo["lineas"],
            "tipo_detectado": parseo["tipo_detectado"],
            "coincidencias": parseo["coincidencias"],
            "tipo_usado": tipo_final,
        }
        return resultado
