"""Rutas API de decisiones: simular, comparar, optimizar y Monte Carlo."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo
from apps.laboratorio.schemas.responses.envelopes import exito

RUTA_SIMULAR = "/laboratorio/api/v1/projects/{proyecto_id}/simulate"
RUTA_SIMS = "/laboratorio/api/v1/projects/{proyecto_id}/simulations"
RUTA_COMPARAR = "/laboratorio/api/v1/projects/{proyecto_id}/compare"
RUTA_COMPARACION = "/laboratorio/api/v1/comparisons/{comparacion_id}"
RUTA_INFORME = RUTA_COMPARACION + "/report.html"
RUTA_OPTIMIZAR = "/laboratorio/api/v1/scenarios/{escenario_id}/optimize"
RUTA_APLICAR = "/laboratorio/api/v1/optimizations/{optimizacion_id}/apply"
RUTA_MONTE = "/laboratorio/api/v1/projects/{proyecto_id}/monte-carlo"
RUTA_MONTE_COMPARA = "/laboratorio/api/v1/projects/{proyecto_id}/monte-carlo/comparar"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_decisiones")
    motor_mc = app.contenedor.obtener("motor_monte_carlo")

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

    def _monte(ctx):
        return exito(motor_mc.simular(ctx.json()))

    def _monte_compara(ctx):
        return exito(motor_mc.comparar(ctx.json()))

    app.registrar("POST", RUTA_SIMULAR, _simular, PermisoCodigo.SIMULAR, "Simular evolucion temporal")
    app.registrar("GET", RUTA_SIMS, _sims, PermisoCodigo.VER, "Listar simulaciones")
    app.registrar("POST", RUTA_COMPARAR, _comparar, PermisoCodigo.COMPARAR, "Comparar escenarios evaluados")
    app.registrar("GET", RUTA_COMPARACION, _comparacion, PermisoCodigo.VER, "Obtener comparacion")
    app.registrar("GET", RUTA_INFORME, _informe, PermisoCodigo.VER, "Informe HTML de la comparacion")
    app.registrar("POST", RUTA_OPTIMIZAR, _optimizar, PermisoCodigo.OPTIMIZAR, "Sugerir optimizacion")
    app.registrar("POST", RUTA_APLICAR, _aplicar, PermisoCodigo.OPTIMIZAR, "Aplicar optimizacion como escenario nuevo")
    app.registrar("POST", RUTA_MONTE, _monte, PermisoCodigo.SIMULAR, "Monte Carlo reproducible con IC95 y convergencia")
    app.registrar("POST", RUTA_MONTE_COMPARA, _monte_compara, PermisoCodigo.COMPARAR, "Comparar configuraciones con Monte Carlo")
