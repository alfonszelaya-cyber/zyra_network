"""LAB-CORE: evaluar escenario A/B/C dejando evidencia completa."""

from apps.laboratorio.application.commands.scenario_commands import (
    ComandoEvaluarEscenario,
)
from apps.laboratorio.application.dto.scenario_dtos import (
    escenario_a_dict,
    evaluacion_a_dict,
)
from apps.laboratorio.domain.evaluation import Evaluacion
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.domain.scenario import evaluate_scenario
from apps.laboratorio.events.domain.scenario_events import escenario_evaluado
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.shared.models.identifiers import nuevo_id


class CasoEvaluarEscenario:
    def __init__(
        self, repo_escenarios, repo_evaluaciones, repo_proyectos,
        repo_historial, bus, outbox, cliente_zyra, auditoria,
    ):
        self._escenarios = repo_escenarios
        self._evaluaciones = repo_evaluaciones
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._bus = bus
        self._outbox = outbox
        self._cliente = cliente_zyra
        self._auditoria = auditoria

    def ejecutar(self, comando: ComandoEvaluarEscenario, identidad) -> dict:
        if not isinstance(comando, ComandoEvaluarEscenario):
            raise ValueError("Se esperaba ComandoEvaluarEscenario.")
        escenario = self._escenarios.obtener_exigir(comando.escenario_id)
        proyecto = self._proyectos.obtener_exigir(str(escenario.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        metricas = evaluate_scenario(escenario)
        evaluacion = Evaluacion(
            id=nuevo_id("eva"),
            escenario_id=escenario.id,
            proyecto_id=proyecto.id,
            metricas=metricas,
            nota=comando.nota,
        )
        self._evaluaciones.agregar(evaluacion)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"),
            proyecto_id=proyecto.id,
            autor_zid=identidad.zid,
            accion="escenario.evaluado",
            detalle={
                "escenario_id": str(escenario.id),
                "puntaje_total": metricas["puntaje_total"],
            },
        ))
        self._bus.publicar(escenario_evaluado(
            str(escenario.id), str(proyecto.id),
            escenario.tipo.value, metricas["puntaje_total"], identidad.zid,
        ))
        sellado = self._sellar()
        self._auditoria.registrar(
            identidad, "escenario.evaluar", str(escenario.id), "exito",
            {"puntaje_total": metricas["puntaje_total"], "sellado": sellado["estado"]},
        )
        return {
            "escenario": escenario_a_dict(escenario),
            "evaluacion": evaluacion_a_dict(evaluacion),
            "sellado": sellado,
        }

    def _sellar(self) -> dict:
        """Ley 1: el sello se entrega solo si ZYRA Core responde; si
        no, queda en outbox con reintentos y se declara pendiente."""
        self._outbox.procesar(self._cliente.entregar)
        estadisticas = self._outbox.estadisticas()
        if estadisticas.get("pendiente", 0) > 0:
            return {
                "estado": "pendiente_red",
                "detalle": "Sello encolado; se entregara cuando ZYRA Core responda.",
                "outbox": estadisticas,
            }
        if estadisticas.get("error", 0) > 0:
            return {"estado": "error_red", "outbox": estadisticas}
        if estadisticas.get("enviado", 0) > 0:
            return {"estado": "sellado_en_zyra", "outbox": estadisticas}
        return {"estado": "sin_carga", "outbox": estadisticas}
