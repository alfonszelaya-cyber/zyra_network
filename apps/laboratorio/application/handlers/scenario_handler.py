"""Manejador de escenarios A/B/C, evaluacion y exportacion SVG."""

from apps.laboratorio.application.commands.scenario_commands import (
    ComandoCrearEscenario,
    ComandoEvaluarEscenario,
)
from apps.laboratorio.application.dto.scenario_dtos import (
    escenario_a_dict,
    evaluacion_a_dict,
)
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.schemas.responses.envelopes import exito
from apps.laboratorio.schemas.shared.common import MIME_SVG
from apps.laboratorio.services.export.svg_exporter import (
    evaluaciones_a_barras,
    grafica_barras,
)
from apps.laboratorio.shared.factories.scenario_factory import EscenarioFactory


class ManejadorEscenarios:
    def __init__(
        self, repo_escenarios, repo_evaluaciones, repo_proyectos,
        caso_evaluar, auditoria,
    ):
        self._escenarios = repo_escenarios
        self._evaluaciones = repo_evaluaciones
        self._proyectos = repo_proyectos
        self._caso_evaluar = caso_evaluar
        self._auditoria = auditoria

    def crear(self, identidad, proyecto_id: str, datos: dict) -> tuple:
        proyecto = self._proyectos.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        comando = ComandoCrearEscenario.desde_request(proyecto_id, datos)
        escenario = EscenarioFactory.crear(
            proyecto.id, comando.tipo, comando.titulo,
            comando.descripcion, comando.parametros,
        )
        self._escenarios.agregar(escenario)
        self._auditoria.registrar(
            identidad, "escenario.crear", str(escenario.id), "exito",
            {"proyecto_id": proyecto_id, "tipo": comando.tipo},
        )
        return exito({"escenario": escenario_a_dict(escenario)}, 201)

    def listar(self, identidad, proyecto_id: str) -> tuple:
        proyecto = self._proyectos.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        escenarios = self._escenarios.listar({"proyecto_id": proyecto.id})
        return exito({"escenarios": [escenario_a_dict(e) for e in escenarios]})

    def evaluar(self, identidad, escenario_id: str, datos: dict) -> tuple:
        nota = str((datos or {}).get("nota", "")).strip()[:500]
        comando = ComandoEvaluarEscenario(escenario_id=escenario_id, nota=nota)
        datos_caso = self._caso_evaluar.ejecutar(comando, identidad)
        return exito(datos_caso)

    def evaluaciones(self, identidad, escenario_id: str) -> tuple:
        escenario = self._escenarios.obtener_exigir(escenario_id)
        proyecto = self._proyectos.obtener_exigir(str(escenario.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        halladas = self._evaluaciones.listar({"escenario_id": escenario_id})
        return exito({
            "evaluaciones": [evaluacion_a_dict(e) for e in halladas],
            "total": len(halladas),
        })

    def exportar_svg(self, identidad, escenario_id: str) -> tuple:
        escenario = self._escenarios.obtener_exigir(escenario_id)
        proyecto = self._proyectos.obtener_exigir(str(escenario.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        halladas = self._evaluaciones.listar({"escenario_id": escenario_id})
        barras = evaluaciones_a_barras([evaluacion_a_dict(e) for e in halladas])
        svg = grafica_barras(
            "Escenario " + escenario.tipo.value + " - " + escenario.titulo, barras
        )
        return 200, svg, {
            "Content-Type": MIME_SVG,
            "Content-Disposition": "inline; filename=escenario_" + str(escenario.id) + ".svg",
        }
