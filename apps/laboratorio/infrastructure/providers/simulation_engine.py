"""Motor de evolucion: proyeccion temporal REAL y determinista.

Modelo documentado (a 1 anio por paso, i = 0..horizonte):
  beneficio_i = beneficio * (1 + crecimiento/100)^i
  costo_i     = costo * 0.98^i        (mejora de eficiencia 2% anual)
  riesgo_i    = min(100, riesgo * (1 + 0.01*i))
  puntaje_i   = min(100, 0.4*(100-costo_i) + 0.4*beneficio_i + 0.2*(100-riesgo_i))
Metricas: punto de equilibrio (primer anio con beneficio > costo),
ROI del horizonte (anios 1..H) y tendencia.
"""
from apps.laboratorio.domain.scenario import Escenario


class MotorEvolucionReal:
    """Proyecta un escenario A/B/C a lo largo del tiempo."""

    EFICIENCIA_ANUAL = 0.02
    RIESGO_ANUAL = 0.01

    def capacidades(self) -> dict:
        return {
            "horizonte_anios": (1, 30),
            "crecimiento_pct": (-50, 200),
            "modelo": "beneficio crece - costo mejora 2pct anual - riesgo +1pct anual",
        }

    def ejecutar(self, escenario: Escenario, horizonte_anios: int, crecimiento_pct: float) -> dict:
        if not isinstance(escenario, Escenario):
            raise ValueError("Se esperaba un Escenario.")
        if not (1 <= int(horizonte_anios) <= 30):
            raise ValueError("horizonte_anios fuera de rango 1-30.")
        if not (-50.0 <= float(crecimiento_pct) <= 200.0):
            raise ValueError("crecimiento_pct fuera de rango -50 a 200.")
        for clave in ("costo", "beneficio", "riesgo"):
            if clave not in escenario.parametros:
                raise ValueError("El escenario requiere el parametro " + clave)
        costo0 = float(escenario.parametros["costo"])
        beneficio0 = float(escenario.parametros["beneficio"])
        riesgo0 = float(escenario.parametros["riesgo"])
        factor_b = 1.0 + float(crecimiento_pct) / 100.0
        serie = []
        sum_beneficio = 0.0
        sum_costo = 0.0
        punto_equilibrio = 0
        for i in range(int(horizonte_anios) + 1):
            beneficio = beneficio0 * (factor_b ** i)
            costo = costo0 * ((1.0 - self.EFICIENCIA_ANUAL) ** i)
            riesgo = min(100.0, riesgo0 * (1.0 + self.RIESGO_ANUAL * i))
            puntaje = min(
                100.0,
                0.4 * (100.0 - costo) + 0.4 * beneficio + 0.2 * (100.0 - riesgo),
            )
            if i >= 1:
                sum_beneficio += beneficio
                sum_costo += costo
                if punto_equilibrio == 0 and beneficio > costo:
                    punto_equilibrio = i
            serie.append({
                "anio": i,
                "costo": round(costo, 4),
                "beneficio": round(beneficio, 4),
                "riesgo": round(riesgo, 4),
                "puntaje": round(puntaje, 4),
            })
        if sum_costo > 0:
            roi = round((sum_beneficio - sum_costo) / sum_costo * 100.0, 2)
        else:
            roi = 0.0
        inicial = serie[0]["puntaje"]
        final = serie[-1]["puntaje"]
        if final > inicial * 1.01:
            tendencia = "creciente"
        elif final < inicial * 0.99:
            tendencia = "decreciente"
        else:
            tendencia = "estable"
        metricas = {
            "punto_equilibrio_anio": punto_equilibrio,
            "roi_pct": roi,
            "puntaje_inicial": inicial,
            "puntaje_final": final,
            "tendencia": tendencia,
        }
        return {"serie": serie, "metricas": metricas}
