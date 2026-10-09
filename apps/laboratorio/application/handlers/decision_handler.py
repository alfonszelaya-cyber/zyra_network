"""Manejador de decisiones: simulacion, comparacion y optimizacion."""
from apps.laboratorio.application.use_cases.decide import (
    CasoAplicarOptimizacion,
    CasoCompararEscenarios,
    CasoOptimizarEscenario,
    CasoSimularEvolucion,
)
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.schemas.responses.envelopes import exito
from apps.laboratorio.services.reports.comparison_report import informe_html


class ManejadorDecisiones:
    def __init__(
        self, caso_simular, caso_comparar, caso_optimizar, caso_aplicar,
        repo_simulaciones, repo_comparaciones, repo_optimizaciones,
        repo_proyectos, repo_escenarios, repo_evaluaciones, auditoria,
    ):
        self._caso_simular = caso_simular
        self._caso_comparar = caso_comparar
        self._caso_optimizar = caso_optimizar
        self._caso_aplicar = caso_aplicar
        self._simulaciones = repo_simulaciones
        self._comparaciones = repo_comparaciones
        self._optimizaciones = repo_optimizaciones
        self._proyectos = repo_proyectos
        self._escenarios = repo_escenarios
        self._evaluaciones = repo_evaluaciones
        self._auditoria = auditoria

    def simular(self, identidad, proyecto_id: str, datos: dict) -> tuple:
        if not isinstance(datos, dict) or not str(datos.get("escenario_id", "")).strip():
            raise ValueError("Falta el campo escenario_id.")
        horizonte = int(datos.get("horizonte_anios", 5))
        crecimiento = float(datos.get("crecimiento_pct", 0.0))
        resultado = self._caso_simular.ejecutar(
            identidad, str(datos["escenario_id"]).strip(), horizonte, crecimiento
        )
        return exito(resultado, 201)

    def listar_simulaciones(self, identidad, proyecto_id: str) -> tuple:
        proyecto = self._proyectos.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        sims = self._simulaciones.listar_por_proyectos([proyecto.id])
        return exito({
            "simulaciones": [CasoSimularEvolucion._a_dict(s) for s in sims],
            "total": len(sims),
        })

    def comparar(self, identidad, proyecto_id: str) -> tuple:
        resultado = self._caso_comparar.ejecutar(identidad, proyecto_id)
        return exito(resultado, 201)

    def obtener_comparacion(self, identidad, comparacion_id: str) -> tuple:
        comparacion = self._comparaciones.obtener_exigir(comparacion_id)
        proyecto = self._proyectos.obtener_exigir(str(comparacion.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        return exito({"comparacion": CasoCompararEscenarios._a_dict(comparacion)})

    def informe_comparacion(self, identidad, comparacion_id: str) -> tuple:
        comparacion = self._comparaciones.obtener_exigir(comparacion_id)
        proyecto = self._proyectos.obtener_exigir(str(comparacion.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        datos = informe_html(comparacion, proyecto.titulo)
        return 200, datos, {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Disposition": "inline; filename=comparacion_" + comparacion_id + ".html",
        }

    def optimizar(self, identidad, escenario_id: str) -> tuple:
        resultado = self._caso_optimizar.ejecutar(identidad, escenario_id)
        return exito(resultado, 201)

    def aplicar(self, identidad, optimizacion_id: str, datos: dict) -> tuple:
        tipo_destino = None
        if isinstance(datos, dict) and str(datos.get("tipo_destino", "")).strip():
            tipo_destino = str(datos["tipo_destino"]).strip()
        resultado = self._caso_aplicar.ejecutar(identidad, optimizacion_id, tipo_destino)
        return exito(resultado, 201)
