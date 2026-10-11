"""Motor MONTE CARLO: simulacion estocastica real y reproducible.

Distribuciones (por variable): normal{media,desv} uniforme{minimo,maximo}
triangular{minimo,modo,maximo}. Semilla determinista (auditable).
Formula declarada: puntaje = (w_b*beneficio + w_c*(100-costo)
+ w_r*(100-riesgo)) / suma_pesos, acotado 0..100.
Estadisticas: media, desv, min, max, P5/P25/P50/P75/P95,
IC95 de la media y convergencia en 10 lotes.
"""
import math
import random

DISTRIBUCIONES = ("normal", "uniforme", "triangular")
MAX_CORRIDAS = 200_000
DEF_CORRIDAS = 10_000
UMBRAL_DEFECTO = 60.0
LOTES_CONVERGENCIA = 10
PESOS_DEFECTO = {"costo": 1.0, "beneficio": 1.0, "riesgo": 1.0}
VARIABLES_VALIDAS = ("costo", "beneficio", "riesgo")


def _numero(valor, nombre):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError("Parametro " + nombre + " debe ser numerico.")
    return float(valor)


class MotorMonteCarlo:
    """Simulacion Monte Carlo con semilla reproducible."""

    def capacidades(self) -> dict:
        return {
            "distribuciones": DISTRIBUCIONES,
            "corridas": {"defecto": DEF_CORRIDAS, "max": MAX_CORRIDAS},
            "salidas": (
                "media", "desv", "min", "max",
                "p5", "p25", "p50", "p75", "p95",
                "ic95", "prob_alcanza_umbral", "convergencia",
            ),
            "reproducible": "semilla entera opcional",
            "formula": (
                "puntaje = (w_b*beneficio + w_c*(100-costo)"
                " + w_r*(100-riesgo)) / (w_b+w_c+w_r)"
            ),
            "rango": "variables y puntaje acotados a 0..100",
        }

    @staticmethod
    def _muestrear(rng, definicion, nombre):
        dist = str(definicion.get("dist", "")).strip()
        if dist == "normal":
            media = _numero(definicion.get("media"), nombre + ".media")
            desv = _numero(definicion.get("desv"), nombre + ".desv")
            if desv < 0:
                raise ValueError(nombre + ".desv no puede ser negativa.")
            return rng.gauss(media, desv)
        if dist == "uniforme":
            bajo = _numero(definicion.get("minimo"), nombre + ".minimo")
            alto = _numero(definicion.get("maximo"), nombre + ".maximo")
            if bajo > alto:
                raise ValueError(nombre + ": minimo no puede superar maximo.")
            return rng.uniform(bajo, alto)
        if dist == "triangular":
            bajo = _numero(definicion.get("minimo"), nombre + ".minimo")
            modo = _numero(definicion.get("modo"), nombre + ".modo")
            alto = _numero(definicion.get("maximo"), nombre + ".maximo")
            if not (bajo <= modo <= alto):
                raise ValueError(nombre + ": requiere minimo <= modo <= maximo.")
            return rng.triangular(bajo, alto, modo)
        raise ValueError(
            nombre + ": distribucion desconocida " + repr(dist)
            + ". Validas: " + ", ".join(DISTRIBUCIONES)
        )

    @staticmethod
    def _percentil(ordenados, q):
        if not ordenados:
            return 0.0
        indice = max(0, min(
            len(ordenados) - 1,
            math.ceil(q / 100.0 * len(ordenados)) - 1,
        ))
        return ordenados[indice]

    def simular(self, config) -> dict:
        if not isinstance(config, dict):
            raise ValueError("Configuracion debe ser un objeto.")
        variables = config.get("variables")
        if not isinstance(variables, dict) or not variables:
            raise ValueError(
                "variables requiere costo, beneficio y riesgo."
            )
        for nombre in variables:
            if nombre not in VARIABLES_VALIDAS:
                raise ValueError(
                    "Variable desconocida: " + repr(nombre)
                    + ". Validas: " + ", ".join(VARIABLES_VALIDAS)
                )
        faltantes = [n for n in VARIABLES_VALIDAS if n not in variables]
        if faltantes:
            raise ValueError(
                "Faltan variables obligatorias: " + ", ".join(faltantes)
            )
        pesos_crudos = config.get("pesos", {})
        if not isinstance(pesos_crudos, dict):
            raise ValueError("pesos debe ser un objeto.")
        pesos = dict(PESOS_DEFECTO)
        for clave, valor in pesos_crudos.items():
            if clave not in VARIABLES_VALIDAS:
                raise ValueError("Peso desconocido: " + repr(clave))
            numero = _numero(valor, "pesos." + clave)
            if numero < 0:
                raise ValueError("pesos." + clave + " no puede ser negativo.")
            pesos[clave] = numero
        total_pesos = sum(pesos.values())
        if total_pesos <= 0:
            raise ValueError("La suma de pesos debe ser mayor que cero.")
        corridas = config.get("corridas", DEF_CORRIDAS)
        if isinstance(corridas, bool) or not isinstance(corridas, int):
            raise ValueError("corridas debe ser entero.")
        if corridas < 1 or corridas > MAX_CORRIDAS:
            raise ValueError(
                "corridas debe estar entre 1 y " + str(MAX_CORRIDAS)
            )
        umbral = _numero(config.get("umbral", UMBRAL_DEFECTO), "umbral")
        if not 0.0 <= umbral <= 100.0:
            raise ValueError("umbral debe estar entre 0 y 100.")
        semilla = config.get("semilla")
        if semilla is not None and (
            isinstance(semilla, bool) or not isinstance(semilla, int)
        ):
            raise ValueError("semilla debe ser entera.")
        rng = random.Random(semilla)
        puntajes = []
        acotados = 0
        peso_b = pesos["beneficio"]
        peso_c = pesos["costo"]
        peso_r = pesos["riesgo"]
        divisor = total_pesos
        for _ in range(corridas):
            costo = self._muestrear(rng, variables["costo"], "costo")
            beneficio = self._muestrear(rng, variables["beneficio"], "beneficio")
            riesgo = self._muestrear(rng, variables["riesgo"], "riesgo")
            for crudo in (costo, beneficio, riesgo):
                if crudo < 0.0 or crudo > 100.0:
                    acotados += 1
            costo = max(0.0, min(100.0, costo))
            beneficio = max(0.0, min(100.0, beneficio))
            riesgo = max(0.0, min(100.0, riesgo))
            puntaje = (
                peso_b * beneficio
                + peso_c * (100.0 - costo)
                + peso_r * (100.0 - riesgo)
            ) / divisor
            puntajes.append(max(0.0, min(100.0, puntaje)))
        ordenados = sorted(puntajes)
        n = float(corridas)
        media = sum(puntajes) / n
        varianza = sum((p - media) * (p - media) for p in puntajes) / max(1.0, n - 1.0)
        desv = math.sqrt(varianza)
        se = desv / math.sqrt(n)
        lote = max(1, corridas // LOTES_CONVERGENCIA)
        convergencia = []
        acumulado = 0.0
        for indice in range(LOTES_CONVERGENCIA):
            inicio = indice * lote
            fin = inicio + lote if indice < LOTES_CONVERGENCIA - 1 else corridas
            acumulado += sum(puntajes[inicio:fin])
            convergencia.append(round(acumulado / float(fin), 4))
        alcanzados = sum(1 for p in puntajes if p >= umbral)
        return {
            "n": corridas,
            "semilla": semilla,
            "formula": self.capacidades()["formula"],
            "variables": variables,
            "pesos": pesos,
            "umbral": umbral,
            "media": round(media, 4),
            "desv": round(desv, 4),
            "min": round(ordenados[0], 4),
            "max": round(ordenados[-1], 4),
            "p5": round(self._percentil(ordenados, 5), 4),
            "p25": round(self._percentil(ordenados, 25), 4),
            "p50": round(self._percentil(ordenados, 50), 4),
            "p75": round(self._percentil(ordenados, 75), 4),
            "p95": round(self._percentil(ordenados, 95), 4),
            "ic95": [
                round(max(0.0, media - 1.96 * se), 4),
                round(min(100.0, media + 1.96 * se), 4),
            ],
            "prob_alcanza_umbral": round(alcanzados / n, 4),
            "convergencia": convergencia,
            "valores_acotados": acotados,
        }

    def comparar(self, configs) -> dict:
        if not isinstance(configs, list) or len(configs) < 2:
            raise ValueError("comparar requiere al menos 2 configuraciones.")
        tabla = []
        for indice, entrada in enumerate(configs):
            if not isinstance(entrada, dict):
                raise ValueError("Cada configuracion debe ser un objeto.")
            nombre = str(entrada.get("nombre", "config-" + str(indice + 1)))
            config = dict(entrada)
            config.pop("nombre", None)
            resultado = self.simular(config)
            tabla.append({
                "nombre": nombre,
                "media": resultado["media"],
                "p50": resultado["p50"],
                "ic95": resultado["ic95"],
                "prob_alcanza_umbral": resultado["prob_alcanza_umbral"],
            })
        orden = sorted(tabla, key=lambda f: f["media"], reverse=True)
        return {
            "ganador": orden[0]["nombre"],
            "brecha": round(orden[0]["media"] - orden[1]["media"], 4),
            "ranking": orden,
            "criterio": "mayor media de puntaje",
        }
