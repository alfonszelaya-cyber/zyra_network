"""Rutas API del 4D: timeline, lighting e interactions."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

RUTA_TIMELINE = "/laboratorio/api/v1/scenes/{escena_id}/timeline"
RUTA_LIGHTING = "/laboratorio/api/v1/scenes/{escena_id}/lighting"
RUTA_INTERACCIONES = "/laboratorio/api/v1/scenes/{escena_id}/interactions"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_cuatro_d")

    def _crear_timeline(ctx):
        return manejador.crear_timeline(ctx.identidad, ctx.ruta_params["escena_id"], ctx.json())

    def _obtener_timeline(ctx):
        return manejador.obtener_timeline(ctx.identidad, ctx.ruta_params["escena_id"])

    def _crear_luz(ctx):
        return manejador.crear_luz(ctx.identidad, ctx.ruta_params["escena_id"], ctx.json())

    def _obtener_luz(ctx):
        return manejador.obtener_luz(ctx.identidad, ctx.ruta_params["escena_id"])

    def _crear_interaccion(ctx):
        return manejador.crear_interaccion(ctx.identidad, ctx.ruta_params["escena_id"], ctx.json())

    def _listar_interacciones(ctx):
        return manejador.listar_interacciones(ctx.identidad, ctx.ruta_params["escena_id"])

    app.registrar("POST", RUTA_TIMELINE, _crear_timeline, PermisoCodigo.EDITAR_4D, "Crear linea de tiempo")
    app.registrar("GET", RUTA_TIMELINE, _obtener_timeline, PermisoCodigo.VER, "Obtener linea de tiempo")
    app.registrar("POST", RUTA_LIGHTING, _crear_luz, PermisoCodigo.EDITAR_4D, "Crear programa de luz")
    app.registrar("GET", RUTA_LIGHTING, _obtener_luz, PermisoCodigo.VER, "Obtener programa de luz")
    app.registrar("POST", RUTA_INTERACCIONES, _crear_interaccion, PermisoCodigo.EDITAR_4D, "Crear zona de interaccion")
    app.registrar("GET", RUTA_INTERACCIONES, _listar_interacciones, PermisoCodigo.VER, "Listar interacciones")
