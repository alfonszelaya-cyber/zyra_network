"""Motor de evolucion + GEMELO DIGITAL EN VIVO."""
from apps.laboratorio.domain.scenario import Escenario

TIPOS_FUENTE = ("sensor", "api", "csv", "manual")


class MotorEvolucionReal:
    EFICIENCIA_ANUAL = 0.02
    RIESGO_ANUAL = 0.01

    def capacidades(self) -> dict:
        return {"horizonte_anios": (1, 30), "crecimiento_pct": (-50, 200),
                "modelo": "beneficio crece - costo mejora 2pct anual - riesgo +1pct anual"}

    def ejecutar(self, escenario, horizonte_anios, crecimiento_pct) -> dict:
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
        sum_b = 0.0
        sum_c = 0.0
        equilibrio = 0
        for i in range(int(horizonte_anios) + 1):
            beneficio = beneficio0 * (factor_b ** i)
            costo = costo0 * ((1.0 - self.EFICIENCIA_ANUAL) ** i)
            riesgo = min(100.0, riesgo0 * (1.0 + self.RIESGO_ANUAL * i))
            puntaje = min(100.0, 0.4 * (100.0 - costo) + 0.4 * beneficio + 0.2 * (100.0 - riesgo))
            if i >= 1:
                sum_b += beneficio
                sum_c += costo
                if equilibrio == 0 and beneficio > costo:
                    equilibrio = i
            serie.append({"anio": i, "costo": round(costo, 4), "beneficio": round(beneficio, 4),
                          "riesgo": round(riesgo, 4), "puntaje": round(puntaje, 4)})
        roi = round((sum_b - sum_c) / sum_c * 100.0, 2) if sum_c > 0 else 0.0
        ini = serie[0]["puntaje"]
        fin = serie[-1]["puntaje"]
        tendencia = "creciente" if fin > ini * 1.01 else ("decreciente" if fin < ini * 0.99 else "estable")
        return {"serie": serie, "metricas": {
            "punto_equilibrio_anio": equilibrio, "roi_pct": roi,
            "puntaje_inicial": ini, "puntaje_final": fin, "tendencia": tendencia}}


class GemeloVivo:
    """Gemelo digital en vivo: fuentes reales -> estado -> alertas honestas."""

    def __init__(self):
        self._fuentes = {}
        self._historico = {}
        self._actualizaciones = 0

    def capacidades(self) -> dict:
        return {"tipos_fuente": TIPOS_FUENTE,
                "salidas": ("estado", "delta", "alertas_por_umbral", "historico")}

    def registrar_fuente(self, id_fuente, tipo, valor, umbral_alto=None, umbral_bajo=None, etiqueta="") -> dict:
        id_limpio = str(id_fuente or "").strip()
        if not id_limpio:
            raise ValueError("id_fuente requerido.")
        if tipo not in TIPOS_FUENTE:
            raise ValueError("tipo desconocido: " + repr(tipo) + ". Validos: " + ", ".join(TIPOS_FUENTE))
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError("valor inicial debe ser numerico.")
        fuente = {"id": id_limpio, "tipo": tipo, "valor": float(valor), "anterior": float(valor),
                  "umbral_alto": None, "umbral_bajo": None, "etiqueta": str(etiqueta or "")[:80],
                  "actualizaciones": 0}
        if umbral_alto is not None:
            if isinstance(umbral_alto, bool) or not isinstance(umbral_alto, (int, float)):
                raise ValueError("umbral_alto debe ser numerico.")
            fuente["umbral_alto"] = float(umbral_alto)
        if umbral_bajo is not None:
            if isinstance(umbral_bajo, bool) or not isinstance(umbral_bajo, (int, float)):
                raise ValueError("umbral_bajo debe ser numerico.")
            fuente["umbral_bajo"] = float(umbral_bajo)
        if (fuente["umbral_alto"] is not None and fuente["umbral_bajo"] is not None
                and fuente["umbral_bajo"] >= fuente["umbral_alto"]):
            raise ValueError("umbral_bajo debe ser menor que umbral_alto.")
        self._fuentes[id_limpio] = fuente
        self._historico[id_limpio] = [float(valor)]
        return dict(fuente)

    def actualizar(self, id_fuente, valor) -> dict:
        id_limpio = str(id_fuente or "").strip()
        fuente = self._fuentes.get(id_limpio)
        if fuente is None:
            raise ValueError("Fuente no registrada: " + id_limpio)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError("valor debe ser numerico.")
        valor = float(valor)
        anterior = fuente["valor"]
        fuente["anterior"] = anterior
        fuente["valor"] = valor
        fuente["actualizaciones"] += 1
        self._actualizaciones += 1
        historico = self._historico.setdefault(id_limpio, [])
        historico.append(valor)
        if len(historico) > 500:
            del historico[:-500]
        alertas = []
        if fuente["umbral_alto"] is not None and valor > fuente["umbral_alto"]:
            alertas.append({"tipo": "umbral_alto_superado", "valor": valor,
                            "umbral": fuente["umbral_alto"], "exceso": round(valor - fuente["umbral_alto"], 6)})
        if fuente["umbral_bajo"] is not None and valor < fuente["umbral_bajo"]:
            alertas.append({"tipo": "umbral_bajo_superado", "valor": valor,
                            "umbral": fuente["umbral_bajo"], "deficit": round(fuente["umbral_bajo"] - valor, 6)})
        return {"id": id_limpio, "valor_anterior": anterior, "valor_nuevo": valor,
                "delta": round(valor - anterior, 6), "alertas": alertas,
                "actualizaciones": self._actualizaciones}

    def estado(self) -> dict:
        fuentes = []
        for id_ in sorted(self._fuentes):
            fuente = dict(self._fuentes[id_])
            fuente["ultimo_delta"] = round(fuente["valor"] - fuente["anterior"], 6)
            fuentes.append(fuente)
        return {"fuentes": fuentes, "total_fuentes": len(fuentes),
                "actualizaciones_totales": self._actualizaciones,
                "historico_puntos": sum(len(v) for v in self._historico.values())}

    def historico(self, id_fuente, limite=50) -> dict:
        id_limpio = str(id_fuente or "").strip()
        if id_limpio not in self._fuentes:
            raise ValueError("Fuente no registrada: " + id_limpio)
        serie = list(self._historico.get(id_limpio, []))
        return {"id": id_limpio, "puntos": len(serie), "valores": serie[-int(limite):]}
