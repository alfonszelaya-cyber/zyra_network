"""Caso de uso: crear un blueprint de diseno con componentes."""
from apps.laboratorio.application.commands.input_commands import ComandoCrearBlueprint
from apps.laboratorio.domain.design import Blueprint
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.shared.enums.creation_type import CreationType
from apps.laboratorio.shared.models.identifiers import nuevo_id


class CasoCrearBlueprint:
    def __init__(self, repo_disenos, repo_proyectos, repo_historial, auditoria):
        self._disenos = repo_disenos
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._auditoria = auditoria

    def ejecutar(self, comando: ComandoCrearBlueprint, identidad) -> dict:
        if not isinstance(comando, ComandoCrearBlueprint):
            raise ValueError("Se esperaba ComandoCrearBlueprint.")
        proyecto = self._proyectos.obtener_exigir(comando.proyecto_id)
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        tipo = CreationType.validar(comando.tipo)
        if not comando.componentes:
            raise ValueError("Un blueprint requiere al menos un componente.")
        blueprint = Blueprint(
            id=nuevo_id("dsn"), proyecto_id=proyecto.id,
            nombre=comando.nombre, tipo_creacion=tipo,
        )
        for c in comando.componentes:
            if not isinstance(c, dict):
                raise ValueError("Cada componente debe ser un objeto.")
            blueprint.agregar_componente(
                str(c.get("nombre", "")), str(c.get("tipo", "")),
                str(c.get("requisitos", "")),
            )
        if not blueprint.es_valido:
            raise ValueError("Blueprint invalido: componentes incompletos.")
        self._disenos.agregar(blueprint)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="blueprint.creado",
            detalle={"blueprint_id": str(blueprint.id),
                     "componentes": len(blueprint.componentes)},
        ))
        self._auditoria.registrar(
            identidad, "diseno.crear", str(blueprint.id), "exito",
            {"componentes": len(blueprint.componentes)},
        )
        return {"blueprint": self._a_dict(blueprint)}

    @staticmethod
    def _a_dict(blueprint) -> dict:
        return {
            "id": str(blueprint.id),
            "proyecto_id": str(blueprint.proyecto_id),
            "nombre": blueprint.nombre,
            "tipo": blueprint.tipo_creacion.value,
            "componentes": list(blueprint.componentes),
            "es_valido": blueprint.es_valido,
            "creado_en": blueprint.creado_en.isoformat(),
        }
