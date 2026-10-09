"""Mapeo fila <-> entidad: unico traductor entre SQL y dominio."""
import json
from datetime import datetime

from apps.laboratorio.domain.evaluation import Evaluacion
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.domain.project import Proyecto
from apps.laboratorio.domain.scenario import Escenario
from apps.laboratorio.shared.enums.creation_type import CreationType
from apps.laboratorio.shared.enums.pipeline_stage import PipelineStage
from apps.laboratorio.shared.enums.project_status import ProjectStatus
from apps.laboratorio.shared.enums.scenario_type import ScenarioType
from apps.laboratorio.shared.helpers.json_helpers import a_json
from apps.laboratorio.shared.models.base import ahora_utc
from apps.laboratorio.shared.models.identifiers import id_desde_texto


def _fecha_desde(texto: str) -> datetime:
    """Convierte texto ISO a datetime; vacio pasa a ahora UTC."""
    if texto:
        return datetime.fromisoformat(texto)
    return ahora_utc()


def _lista_desde(texto: str) -> list:
    """Convierte texto JSON a lista validada."""
    datos = json.loads(texto or "[]")
    if not isinstance(datos, list):
        raise ValueError("Se esperaba una lista JSON.")
    return datos


def _dict_desde(texto: str) -> dict:
    """Convierte texto JSON a dict validado."""
    datos = json.loads(texto or "{}")
    if not isinstance(datos, dict):
        raise ValueError("Se esperaba un objeto JSON.")
    return datos


def proyecto_a_fila(proyecto: Proyecto) -> dict:
    """Proyecto -> fila con nombre de columna."""
    if not isinstance(proyecto, Proyecto):
        raise ValueError("Se esperaba un Proyecto.")
    return {
        "id": str(proyecto.id),
        "titulo": proyecto.titulo,
        "descripcion": proyecto.descripcion,
        "tipo": proyecto.tipo_creacion.value,
        "etapa": proyecto.etapa_actual.value,
        "estado": proyecto.estado.value,
        "propietario_zid": proyecto.propietario_zid,
        "etiquetas": a_json(list(proyecto.etiquetas)),
        "creado_en": proyecto.creado_en.isoformat(),
        "actualizado_en": proyecto.actualizado_en.isoformat(),
    }


def fila_a_proyecto(fila) -> Proyecto:
    """Fila -> Proyecto de dominio."""
    return Proyecto(
        id=id_desde_texto("proy", fila["id"]),
        titulo=fila["titulo"],
        descripcion=fila["descripcion"] or "",
        tipo_creacion=CreationType(fila["tipo"]),
        etapa_actual=PipelineStage(fila["etapa"]),
        estado=ProjectStatus(fila["estado"]),
        propietario_zid=fila["propietario_zid"],
        etiquetas=_lista_desde(fila["etiquetas"]),
        creado_en=_fecha_desde(fila["creado_en"]),
        actualizado_en=_fecha_desde(fila["actualizado_en"]),
    )


def escenario_a_fila(escenario: Escenario) -> dict:
    """Escenario -> fila con nombre de columna."""
    if not isinstance(escenario, Escenario):
        raise ValueError("Se esperaba un Escenario.")
    return {
        "id": str(escenario.id),
        "proyecto_id": str(escenario.proyecto_id),
        "tipo": escenario.tipo.value,
        "titulo": escenario.titulo,
        "descripcion": escenario.descripcion,
        "parametros": a_json(dict(escenario.parametros)),
        "creado_en": escenario.creado_en.isoformat(),
        "actualizado_en": escenario.actualizado_en.isoformat(),
    }


def fila_a_escenario(fila) -> Escenario:
    """Fila -> Escenario de dominio."""
    return Escenario(
        id=id_desde_texto("esc", fila["id"]),
        proyecto_id=id_desde_texto("proy", fila["proyecto_id"]),
        tipo=ScenarioType(fila["tipo"]),
        titulo=fila["titulo"],
        descripcion=fila["descripcion"] or "",
        parametros=_dict_desde(fila["parametros"]),
        creado_en=_fecha_desde(fila["creado_en"]),
        actualizado_en=_fecha_desde(fila["actualizado_en"]),
    )


def evaluacion_a_fila(evaluacion: Evaluacion) -> dict:
    """Evaluacion -> fila con nombre de columna."""
    if not isinstance(evaluacion, Evaluacion):
        raise ValueError("Se esperaba una Evaluacion.")
    return {
        "id": str(evaluacion.id),
        "escenario_id": str(evaluacion.escenario_id),
        "proyecto_id": str(evaluacion.proyecto_id),
        "metricas": a_json(dict(evaluacion.metricas)),
        "nota": evaluacion.nota,
        "creado_en": evaluacion.creado_en.isoformat(),
        "actualizado_en": evaluacion.actualizado_en.isoformat(),
    }


def fila_a_evaluacion(fila) -> Evaluacion:
    """Fila -> Evaluacion de dominio."""
    return Evaluacion(
        id=id_desde_texto("eva", fila["id"]),
        escenario_id=id_desde_texto("esc", fila["escenario_id"]),
        proyecto_id=id_desde_texto("proy", fila["proyecto_id"]),
        metricas=_dict_desde(fila["metricas"]),
        nota=fila["nota"] or "",
        creado_en=_fecha_desde(fila["creado_en"]),
        actualizado_en=_fecha_desde(fila["actualizado_en"]),
    )


def historial_a_fila(entrada: EntradaHistorial) -> dict:
    """EntradaHistorial -> fila con nombre de columna."""
    if not isinstance(entrada, EntradaHistorial):
        raise ValueError("Se esperaba una EntradaHistorial.")
    return {
        "id": str(entrada.id),
        "proyecto_id": str(entrada.proyecto_id),
        "autor_zid": entrada.autor_zid,
        "accion": entrada.accion,
        "detalle": a_json(dict(entrada.detalle)),
        "creado_en": entrada.creado_en.isoformat(),
        "actualizado_en": entrada.actualizado_en.isoformat(),
    }


def fila_a_historial(fila) -> EntradaHistorial:
    """Fila -> EntradaHistorial de dominio."""
    return EntradaHistorial(
        id=id_desde_texto("his", fila["id"]),
        proyecto_id=id_desde_texto("proy", fila["proyecto_id"]),
        autor_zid=fila["autor_zid"],
        accion=fila["accion"],
        detalle=_dict_desde(fila["detalle"]),
        creado_en=_fecha_desde(fila["creado_en"]),
        actualizado_en=_fecha_desde(fila["actualizado_en"]),
    )
