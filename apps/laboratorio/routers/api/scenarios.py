"""Rutas API de escenarios A/B/C y evaluacion LAB-CORE."""

from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

PREFIJO = "/laboratorio/api/v1/projects/{proyecto_id}/scenarios"
RUTA_EVALUAR = PREFIJO + "/{escenario_id}/evaluate"
RUTA_EVALUACIONES = "/laboratorio/api/v1/scenarios/{escenario_id}/evaluations"
RUTA_EXPORT = "/laboratorio/api/v1/scenarios/{escenario_id}/export.svg"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_escenarios")

    def _crear(ctx):
        return manejador.crear(ctx.identidad, ctx.ruta_params["proyecto_id"], ctx.json())

    def _listar(ctx):
        return manejador.listar(ctx.identidad, ctx.ruta_params["proyecto_id"])

    def _evaluar(ctx):
        return manejador.evaluar(ctx.identidad, ctx.ruta_params["escenario_id"], ctx.json_opcional())

    def _evaluaciones(ctx):
        return manejador.evaluaciones(ctx.identidad, ctx.ruta_params["escenario_id"])

    def _export(ctx):
        return manejador.exportar_svg(ctx.identidad, ctx.ruta_params["escenario_id"])

    app.registrar("POST", PREFIJO, _crear, PermisoCodigo.SIMULAR, "Crear escenario A/B/C")
    app.registrar("GET", PREFIJO, _listar, PermisoCodigo.VER, "Listar escenarios del proyecto")
    app.registrar("POST", RUTA_EVALUAR, _evaluar, PermisoCodigo.EVALUAR, "Evaluar escenario (LAB-CORE)")
    app.registrar("GET", RUTA_EVALUACIONES, _evaluaciones, PermisoCodigo.VER, "Evaluaciones del escenario")
    app.registrar("GET", RUTA_EXPORT, _export, PermisoCodigo.VER, "Exportar grafica SVG de evaluaciones")
