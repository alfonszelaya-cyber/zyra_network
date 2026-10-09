"""Motor de optimizacion: reglas concretas y parametros calculados.

Reglas oficiales (todas verificables sobre los parametros 0-100):
  costo > 50     -> reducir 20%
  riesgo > 40    -> mitigar 30%
  beneficio < 60 -> aumentar 15%
Los resultados se acotan a 0-100. El puntaje proyectado se
calcula con evaluate_scenario (formula oficial, sin duplicar).
"""
from apps.laboratorio.domain.scenario import Escenario, evaluate_scenario
from apps.laboratorio.shared.enums.scenario_type import ScenarioType
from apps.laboratorio.shared.models.identifiers import nuevo_id

REGLA_COSTO = {"umbral": 50.0, "factor": 0.80, "accion": "Reducir costo un 20%"}
REGLA_RIESGO = {"umbral": 40.0, "factor": 0.70, "accion": "Mitigar riesgo un 30%"}
REGLA_BENEFICIO = {"umbral": 60.0, "factor": 1.15, "accion": "Aumentar beneficio un 15%"}


class MotorOptimizacionReal:
    """Sugiere mejoras con impacto estimado por dimension."""

    def capacidades(self) -> dict:
        return {
            "reglas": {
                "costo": REGLA_COSTO,
                "riesgo": REGLA_RIESGO,
                "beneficio": REGLA_BENEFICIO,
            },
            "rango": "parametros acotados a 0-100",
        }

    def sugerir(self, parametros: dict) -> dict:
        if not isinstance(parametros, dict):
            raise ValueError("Los parametros deben ser un objeto.")
        for clave in ("costo", "beneficio", "riesgo"):
            if clave not in parametros:
                raise ValueError("Falta el parametro " + clave)
            valor = parametros[clave]
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise ValueError("Parametro " + clave + " debe ser numerico.")
        costo = float(parametros["costo"])
        beneficio = float(parametros["beneficio"])
        riesgo = float(parametros["riesgo"])
        recomendaciones = []
        nuevo_costo = costo
        nuevo_beneficio = beneficio
        nuevo_riesgo = riesgo
        if costo > REGLA_COSTO["umbral"]:
            nuevo_costo = round(costo * REGLA_COSTO["factor"], 4)
            recomendaciones.append({
                "dimension": "costo",
                "accion": REGLA_COSTO["accion"],
                "de": round(costo, 2),
                "a": nuevo_costo,
                "razon": "costo " + str(round(costo, 1)) + " supera el umbral 50",
            })
        if riesgo > REGLA_RIESGO["umbral"]:
            nuevo_riesgo = round(riesgo * REGLA_RIESGO["factor"], 4)
            recomendaciones.append({
                "dimension": "riesgo",
                "accion": REGLA_RIESGO["accion"],
                "de": round(riesgo, 2),
                "a": nuevo_riesgo,
                "razon": "riesgo " + str(round(riesgo, 1)) + " supera el umbral 40",
            })
        if beneficio < REGLA_BENEFICIO["umbral"]:
            nuevo_beneficio = min(100.0, round(beneficio * REGLA_BENEFICIO["factor"], 4))
            recomendaciones.append({
                "dimension": "beneficio",
                "accion": REGLA_BENEFICIO["accion"],
                "de": round(beneficio, 2),
                "a": nuevo_beneficio,
                "razon": "beneficio " + str(round(beneficio, 1)) + " esta bajo el umbral 60",
            })
        optimizados = {
            "costo": max(0.0, min(100.0, nuevo_costo)),
            "beneficio": max(0.0, min(100.0, nuevo_beneficio)),
            "riesgo": max(0.0, min(100.0, nuevo_riesgo)),
        }
        return {"recomendaciones": recomendaciones, "parametros_optimizados": optimizados}

    def puntaje_proyectado(self, parametros_optimizados: dict) -> float:
        """Puntaje oficial del escenario optimizado (sin duplicar formula)."""
        temporal = Escenario(
            id=nuevo_id("esc"),
            proyecto_id=nuevo_id("proy"),
            tipo=ScenarioType.A,
            titulo="proyeccion temporal",
            parametros=dict(parametros_optimizados),
        )
        return float(evaluate_scenario(temporal)["puntaje_total"])
