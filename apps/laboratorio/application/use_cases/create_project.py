"""Caso de uso: crear proyecto con evidencia completa."""

from apps.laboratorio.application.commands.project_commands import (
    ComandoCrearProyecto,
)
from apps.laboratorio.application.dto.project_dtos import proyecto_a_dict
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.events.domain.project_events import proyecto_creado
from apps.laboratorio.shared.factories.project_factory import ProyectoFactory
from apps.laboratorio.shared.models.identifiers import nuevo_id


class CasoCrearProyecto:
    def __init__(self, repo_proyectos, repo_historial, bus, auditoria):
        self._repo = repo_proyectos
        self._historial = repo_historial
        self._bus = bus
        self._auditoria = auditoria

    def ejecutar(self, comando: ComandoCrearProyecto, identidad) -> dict:
        if not isinstance(comando, ComandoCrearProyecto):
            raise ValueError("Se esperaba ComandoCrearProyecto.")
        proyecto = ProyectoFactory.crear(
            comando.titulo,
            comando.descripcion,
            comando.tipo,
            comando.propietario_zid,
            list(comando.etiquetas),
        )
        self._repo.agregar(proyecto)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"),
            proyecto_id=proyecto.id,
            autor_zid=identidad.zid,
            accion="proyecto.creado",
            detalle={"tipo": comando.tipo, "titulo": proyecto.titulo},
        ))
        self._bus.publicar(proyecto_creado(str(proyecto.id), proyecto.titulo, identidad.zid))
        self._auditoria.registrar(
            identidad, "proyecto.crear", str(proyecto.id), "exito",
            {"tipo": comando.tipo},
        )
        return {"proyecto": proyecto_a_dict(proyecto)}
