"""Manejador de documentos: previsualizar y crear proyecto."""

from apps.laboratorio.application.services.document_parser import (
    parsear_documento,
)
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorDocumentos:
    def __init__(self, caso_desde_documento, auditoria):
        if caso_desde_documento is None:
            raise ValueError("ManejadorDocumentos requiere su caso de uso.")
        self._caso = caso_desde_documento
        self._auditoria = auditoria

    def previsualizar(self, identidad, datos: dict) -> tuple:
        if not isinstance(datos, dict) or not str(datos.get("documento", "")).strip():
            raise ValueError("Falta el campo documento.")
        parseo = parsear_documento(str(datos["documento"]))
        self._auditoria.registrar(
            identidad, "documento.previsualizar", "parse-document", "exito",
            {"tipo": parseo["tipo"], "palabras": parseo["palabras"]},
        )
        return exito({"parseo": parseo})

    def crear_proyecto(self, identidad, datos: dict) -> tuple:
        if not isinstance(datos, dict) or not str(datos.get("documento", "")).strip():
            raise ValueError("Falta el campo documento.")
        titulo = datos.get("titulo")
        if titulo is not None:
            titulo = str(titulo)
        tipo = datos.get("tipo")
        if tipo is not None and str(tipo).strip():
            tipo = str(tipo).strip()
        else:
            tipo = None
        resultado = self._caso.ejecutar(
            identidad, str(datos["documento"]), titulo, tipo
        )
        self._auditoria.registrar(
            identidad, "documento.crear_proyecto",
            resultado["proyecto"]["id"], "exito",
            {"tipo": resultado["proyecto"]["tipo"]},
        )
        return exito(resultado, 201)
