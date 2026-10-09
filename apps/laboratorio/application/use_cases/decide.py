"""Casos de uso de decision: simular, comparar, optimizar y aplicar.

Todos dejan evidencia completa: persistencia, historial y
auditoria. Los puntajes salen SIEMPRE de evaluate_scenario
(formula oficial, cero duplicacion).
"""
from apps.laboratorio.domain.comparison import Comparacion
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.domain.optimization import (
    ESTADO_SUGERIDA,
    PropuestaOptimizacion,
)
from apps.laboratorio.domain.scenario import evaluate_scenario
from apps.laboratorio.domain.simulation import SimulacionEvolucion
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.shared.factories.scenario_factory import EscenarioFactory
from apps.laboratorio.shared.enums.scenario_type import ScenarioType
from apps.laboratorio.shared.models.identifiers import nuevo_id
from apps.laboratorio.services.reports.comparison_report import informe_html


class CasoSimularEvolucion:
    def __init__(self, repo_simulaciones, repo_escenarios, repo_proyectos, repo_historial, motor, auditoria):
        self._simulaciones = repo_simulaciones
        self._escenarios = repo_escenarios
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._motor = motor
        self._auditoria = auditoria

    def ejecutar(self, identidad, escenario_id: str, horizonte: int, crecimiento: float) -> dict:
        escenario = self._escenarios.obtener_exigir(escenario_id)
        proyecto = self._proyectos.obtener_exigir(str(escenario.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        resultado = self._motor.ejecutar(escenario, int(horizonte), float(crecimiento))
        sim = SimulacionEvolucion(
            id=nuevo_id("sim"), proyecto_id=proyecto.id, escenario_id=escenario.id,
            horizonte_anios=int(horizonte), crecimiento_pct=float(crecimiento),
            serie=resultado["serie"], metricas=resultado["metricas"],
        )
        self._simulaciones.agregar(sim)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="simulacion.ejecutada",
            detalle={"simulacion_id": str(sim.id),
                     "escenario_id": str(escenario.id),
                     "horizonte": sim.horizonte_anios},
        ))
        self._auditoria.registrar(
            identidad, "simulacion.ejecutar", str(sim.id), "exito",
            {"horizonte": sim.horizonte_anios,
             "punto_equilibrio": resultado["metricas"]["punto_equilibrio_anio"]},
        )
        return {"simulacion": self._a_dict(sim)}

    @staticmethod
    def _a_dict(sim) -> dict:
        return {
            "id": str(sim.id),
            "proyecto_id": str(sim.proyecto_id),
            "escenario_id": str(sim.escenario_id),
            "horizonte_anios": sim.horizonte_anios,
            "crecimiento_pct": sim.crecimiento_pct,
            "serie": list(sim.serie),
            "metricas": dict(sim.metricas),
            "total_anios": sim.total_anios,
            "creado_en": sim.creado_en.isoformat(),
        }


class CasoCompararEscenarios:
    def __init__(self, repo_comparaciones, repo_escenarios, repo_evaluaciones, repo_proyectos, repo_historial, motor, auditoria):
        self._comparaciones = repo_comparaciones
        self._escenarios = repo_escenarios
        self._evaluaciones = repo_evaluaciones
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._motor = motor
        self._auditoria = auditoria

    def ejecutar(self, identidad, proyecto_id: str) -> dict:
        proyecto = self._proyectos.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        escenarios = self._escenarios.listar({"proyecto_id": proyecto.id})
        evaluaciones = self._evaluaciones.listar({"proyecto_id": proyecto.id})
        ultima_por_escenario = {}
        for ev in evaluaciones:
            clave = str(ev.escenario_id)
            if clave not in ultima_por_escenario:
                ultima_por_escenario[clave] = ev
        participantes = []
        for esc in escenarios:
            ev = ultima_por_escenario.get(str(esc.id))
            if ev is None:
                continue
            participantes.append({
                "escenario_id": str(esc.id),
                "tipo": esc.tipo.value,
                "titulo": esc.titulo,
                "puntaje": ev.puntaje_total,
                "metricas": dict(ev.metricas),
            })
        if len(participantes) < 2:
            raise ValueError(
                "Se requieren al menos 2 escenarios con evaluacion para comparar; "
                "el proyecto tiene " + str(len(participantes)) + "."
            )
        veredicto = self._motor.comparar(participantes)
        comparacion = Comparacion(
            id=nuevo_id("cmp"), proyecto_id=proyecto.id,
            participantes=veredicto["participantes"],
            ganador=veredicto["ganador"],
            brecha=veredicto["brecha"],
            detalle=veredicto["detalle"],
            informe="",
        )
        comparacion.informe = informe_html(comparacion, proyecto.titulo).decode("utf-8")
        self._comparaciones.agregar(comparacion)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="comparacion.generada",
            detalle={"comparacion_id": str(comparacion.id),
                     "ganador": comparacion.ganador,
                     "brecha": comparacion.brecha},
        ))
        self._auditoria.registrar(
            identidad, "comparacion.generar", str(comparacion.id), "exito",
            {"participantes": len(participantes), "brecha": comparacion.brecha},
        )
        return {"comparacion": self._a_dict(comparacion)}

    @staticmethod
    def _a_dict(comparacion) -> dict:
        return {
            "id": str(comparacion.id),
            "proyecto_id": str(comparacion.proyecto_id),
            "participantes": list(comparacion.participantes),
            "ganador": comparacion.ganador,
            "brecha": comparacion.brecha,
            "detalle": dict(comparacion.detalle),
            "creado_en": comparacion.creado_en.isoformat(),
        }


class CasoOptimizarEscenario:
    def __init__(self, repo_optimizaciones, repo_escenarios, repo_proyectos, repo_historial, motor, auditoria):
        self._optimizaciones = repo_optimizaciones
        self._escenarios = repo_escenarios
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._motor = motor
        self._auditoria = auditoria

    def ejecutar(self, identidad, escenario_id: str) -> dict:
        escenario = self._escenarios.obtener_exigir(escenario_id)
        proyecto = self._proyectos.obtener_exigir(str(escenario.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        sugerencia = self._motor.sugerir(escenario.parametros)
        if not sugerencia["recomendaciones"]:
            raise ValueError(
                "El escenario ya esta optimizado segun las reglas oficiales: "
                "sin recomendaciones aplicables."
            )
        puntaje_actual = float(evaluate_scenario(escenario)["puntaje_total"])
        puntaje_proyectado = self._motor.puntaje_proyectado(
            sugerencia["parametros_optimizados"]
        )
        propuesta = PropuestaOptimizacion(
            id=nuevo_id("opt"), proyecto_id=proyecto.id, escenario_id=escenario.id,
            recomendaciones=sugerencia["recomendaciones"],
            parametros_optimizados=sugerencia["parametros_optimizados"],
            puntaje_actual=puntaje_actual,
            puntaje_proyectado=puntaje_proyectado,
        )
        self._optimizaciones.agregar(propuesta)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="optimizacion.propuesta",
            detalle={"propuesta_id": str(propuesta.id),
                     "mejora_estimada": propuesta.mejora_estimada},
        ))
        self._auditoria.registrar(
            identidad, "optimizacion.sugerir", str(propuesta.id), "exito",
            {"mejora_estimada": propuesta.mejora_estimada},
        )
        return {"optimizacion": self._a_dict(propuesta)}

    @staticmethod
    def _a_dict(propuesta) -> dict:
        return {
            "id": str(propuesta.id),
            "proyecto_id": str(propuesta.proyecto_id),
            "escenario_id": str(propuesta.escenario_id),
            "recomendaciones": list(propuesta.recomendaciones),
            "parametros_optimizados": dict(propuesta.parametros_optimizados),
            "puntaje_actual": propuesta.puntaje_actual,
            "puntaje_proyectado": propuesta.puntaje_proyectado,
            "mejora_estimada": propuesta.mejora_estimada,
            "estado": propuesta.estado,
            "aplicado_como": propuesta.aplicado_como,
            "creado_en": propuesta.creado_en.isoformat(),
        }


class CasoAplicarOptimizacion:
    def __init__(self, repo_optimizaciones, repo_escenarios, repo_proyectos, repo_historial, auditoria):
        self._optimizaciones = repo_optimizaciones
        self._escenarios = repo_escenarios
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._auditoria = auditoria

    def ejecutar(self, identidad, propuesta_id: str, tipo_destino: str = None) -> dict:
        propuesta = self._optimizaciones.obtener_exigir(propuesta_id)
        escenario_origen = self._escenarios.obtener_exigir(str(propuesta.escenario_id))
        proyecto = self._proyectos.obtener_exigir(str(propuesta.proyecto_id))
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        if tipo_destino is not None and str(tipo_destino).strip():
            tipo = ScenarioType.validar(str(tipo_destino).strip())
        else:
            tipo = escenario_origen.tipo
        escenario_optimizado = EscenarioFactory.crear(
            proyecto.id, tipo,
            titulo=escenario_origen.titulo + " (optimizado)",
            descripcion="Escenario derivado de la propuesta "
            + str(propuesta.id) + " con parametros optimizados.",
            parametros=dict(propuesta.parametros_optimizados),
        )
        self._escenarios.agregar(escenario_optimizado)
        propuesta.marcar_aplicada(str(escenario_optimizado.id))
        self._optimizaciones.actualizar_aplicada(propuesta)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="optimizacion.aplicada",
            detalle={"propuesta_id": str(propuesta.id),
                     "escenario_creado": str(escenario_optimizado.id)},
        ))
        self._auditoria.registrar(
            identidad, "optimizacion.aplicar", str(propuesta.id), "exito",
            {"escenario_creado": str(escenario_optimizado.id)},
        )
        return {
            "optimizacion": CasoOptimizarEscenario._a_dict(propuesta),
            "escenario_creado": {
                "id": str(escenario_optimizado.id),
                "titulo": escenario_optimizado.titulo,
                "tipo": escenario_optimizado.tipo.value,
                "parametros": dict(escenario_optimizado.parametros),
                "puntaje_oficial": evaluate_scenario(escenario_optimizado)["puntaje_total"],
            },
        }
