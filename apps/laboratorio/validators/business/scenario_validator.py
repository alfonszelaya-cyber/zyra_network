"""Validacion de borde para datos de escenarios (el dominio re-valida)."""

from apps.laboratorio.shared.enums.scenario_type import ScenarioType

PARAMETROS_REQUERIDOS = ("costo", "beneficio", "riesgo")


def validar_parametros_evaluacion(parametros) -> dict:
    if not isinstance(parametros, dict):
        raise ValueError("Los parametros deben ser un objeto.")
    limpios = {}
    for clave in PARAMETROS_REQUERIDOS:
        if clave not in parametros:
            raise ValueError("Falta parametro requerido: " + clave)
        valor = parametros[clave]
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError("Parametro " + clave + " debe ser numerico.")
        numero = float(valor)
        if not 0.0 <= numero <= 100.0:
            raise ValueError("Parametro " + clave + " fuera de escala 0-100.")
        limpios[clave] = numero
    return limpios


def validar_datos_escenario(datos) -> dict:
    if not isinstance(datos, dict):
        raise ValueError("Datos de escenario invalidos.")
    tipo = ScenarioType.validar(str(datos.get("tipo", "")))
    titulo = str(datos.get("titulo", "")).strip()
    if not titulo:
        raise ValueError("El escenario requiere titulo.")
    if len(titulo) > 200:
        raise ValueError("Titulo demasiado largo (max 200).")
    descripcion = str(datos.get("descripcion", "")).strip()
    parametros = validar_parametros_evaluacion(datos.get("parametros", {}))
    return {
        "tipo": tipo.value,
        "titulo": titulo,
        "descripcion": descripcion,
        "parametros": parametros,
    }
