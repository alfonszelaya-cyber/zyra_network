"""Serializacion oficial de escenarios y evaluaciones."""


def escenario_a_dict(escenario) -> dict:
    return {
        "id": str(escenario.id),
        "proyecto_id": str(escenario.proyecto_id),
        "tipo": escenario.tipo.value,
        "titulo": escenario.titulo,
        "descripcion": escenario.descripcion,
        "parametros": dict(escenario.parametros),
        "creado_en": escenario.creado_en.isoformat(),
    }


def evaluacion_a_dict(evaluacion) -> dict:
    return {
        "id": str(evaluacion.id),
        "escenario_id": str(evaluacion.escenario_id),
        "proyecto_id": str(evaluacion.proyecto_id),
        "metricas": dict(evaluacion.metricas),
        "puntaje_total": evaluacion.puntaje_total,
        "nota": evaluacion.nota,
        "creado_en": evaluacion.creado_en.isoformat(),
    }
