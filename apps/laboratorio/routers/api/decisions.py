"""Rutas API de decisiones: simular, comparar y optimizar."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

RUTA_SIMULAR = "/laboratorio/api/v1/projects/{proyecto_id}/simulate"
RUTA_SIMS = "/laboratorio/api/v1/projects/{proyecto_id}/simulations"
RUTA_COMPARAR = "/laboratorio/api/v1/projects/{proyecto_id}/compare"
RUTA_COMPARACION = "/laboratorio/api/v1/comparisons/{comparacion_id}"
RUTA_INFORME = RUTA_COMPARACION + "/report.html"
RUTA_OPTIMIZAR = "/laboratorio/api/v1/scenarios/{escenario_id}/optimize"
RUTA_APLICAR = "/laboratorio/api/v1/optimizations/{optimizacion_id}/apply"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_decisiones")

    def _simular(ctx):
        return manejador.simular(ctx.identidad, ctx.ruta_params["proyecto_id"], ctx.json())

    def _sims(ctx):
        return manejador.listar_simulaciones(ctx.identidad, ctx.ruta_params["proyecto_id"])

    def _comparar(ctx):
        return manejador.comparar(ctx.identidad, ctx.ruta_params["proyecto_id"])

    def _comparacion(ctx):
        return manejador.obtener_comparacion(ctx.identidad, ctx.ruta_params["comparacion_id"])

    def _informe(ctx):
        return manejador.informe_comparacion(ctx.identidad, ctx.ruta_params["comparacion_id"])

    def _optimizar(ctx):
        return manejador.optimizar(ctx.identidad, ctx.ruta_params["escenario_id"])

    def _aplicar(ctx):
        return manejador.aplicar(ctx.identidad, ctx.ruta_params["optimizacion_id"], ctx.json_opcional())

    app.registrar("POST", RUTA_SIMULAR, _simular, PermisoCodigo.SIMULAR, "Simular evolucion temporal")
    app.registrar("GET", RUTA_SIMS, _sims, PermisoCodigo.VER, "Listar simulaciones")
    app.registrar("POST", RUTA_COMPARAR, _comparar, PermisoCodigo.COMPARAR, "Comparar escenarios evaluados")
    app.registrar("GET", RUTA_COMPARACION, _comparacion, PermisoCodigo.VER, "Obtener comparacion")
    app.registrar("GET", RUTA_INFORME, _informe, PermisoCodigo.VER, "Informe HTML de la comparacion")
    app.registrar("POST", RUTA_OPTIMIZAR, _optimizar, PermisoCodigo.OPTIMIZAR, "Sugerir optimizacion")
    app.registrar("POST", RUTA_APLICAR, _aplicar, PermisoCodigo.OPTIMIZAR, "Aplicar optimizacion como escenario nuevo")
