"""Motor de comparacion: decision fundamentada con datos reales.

Ordena participantes por puntaje oficial, declara ganador, calcula
la brecha contra el segundo y el desglose por dimension.
"""
DIMENSIONES = ("costo", "beneficio", "riesgo")


class MotorComparacionReal:
    """Compara participantes y produce el veredicto con razones."""

    def capacidades(self) -> dict:
        return {
            "dimensiones": DIMENSIONES,
            "criterio": "puntaje_total oficial (mayor gana)",
            "nota": "menor costo y menor riesgo son mejores",
        }

    def comparar(self, participantes: list) -> dict:
        if not isinstance(participantes, list) or len(participantes) < 2:
            raise ValueError("Se requieren al menos 2 participantes evaluados.")
        ordenados = sorted(
            participantes,
            key=lambda p: float(p.get("puntaje", 0.0)),
            reverse=True,
        )
        ganador = ordenados[0]
        segundo = ordenados[1]
        brecha = round(float(ganador["puntaje"]) - float(segundo["puntaje"]), 4)
        detalle = {}
        for dimension in DIMENSIONES:
            mejor = None
            for p in ordenados:
                valor = (p.get("metricas") or {}).get(dimension)
                if valor is None:
                    continue
                valor = float(valor)
                if mejor is None:
                    mejor = (p, valor)
                else:
                    es_mejor = (
                        valor < mejor[1] if dimension in ("costo", "riesgo")
                        else valor > mejor[1]
                    )
                    if es_mejor:
                        mejor = (p, valor)
            if mejor is not None:
                detalle[dimension] = {
                    "mejor": mejor[0].get("titulo", ""),
                    "valor": mejor[1],
                }
        return {
            "participantes": ordenados,
            "ganador": str(ganador.get("escenario_id", "")),
            "brecha": brecha,
            "detalle": detalle,
        }
