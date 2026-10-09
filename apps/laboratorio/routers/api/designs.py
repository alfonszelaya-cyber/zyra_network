"""Rutas API de blueprints de diseno."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

PREFIJO = "/laboratorio/api/v1/projects/{proyecto_id}/designs"
RUTA_DESIGN = "/laboratorio/api/v1/designs/{design_id}"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_disenos")

    def _crear(ctx):
        return manejador.crear(ctx.identidad, ctx.ruta_params["proyecto_id"], ctx.json())

    def _listar(ctx):
        return manejador.listar(ctx.identidad, ctx.ruta_params["proyecto_id"])

    def _obtener(ctx):
        return manejador.obtener(ctx.identidad, ctx.ruta_params["design_id"])

    app.registrar("POST", PREFIJO, _crear, PermisoCodigo.DISENAR, "Crear blueprint")
    app.registrar("GET", PREFIJO, _listar, PermisoCodigo.VER, "Listar blueprints")
    app.registrar("GET", RUTA_DESIGN, _obtener, PermisoCodigo.VER, "Obtener blueprint")
