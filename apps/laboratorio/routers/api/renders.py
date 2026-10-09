"""Rutas API de renders: escalera fotoreal y canal de profundidad."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

RUTA_RENDER = "/laboratorio/api/v1/scenes/{escena_id}/render"
RUTA_RENDERS = "/laboratorio/api/v1/scenes/{escena_id}/renders"
RUTA_IMAGEN = "/laboratorio/api/v1/renders/{render_id}"
RUTA_PROFUNDIDAD = RUTA_IMAGEN + "/depth.png"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_renders")

    def _renderizar(ctx):
        return manejador.renderizar(ctx.identidad, ctx.ruta_params["escena_id"], ctx.json())

    def _listar(ctx):
        return manejador.listar(ctx.identidad, ctx.ruta_params["escena_id"])

    def _descargar(ctx):
        return manejador.descargar(ctx.identidad, ctx.ruta_params["render_id"])

    def _profundidad(ctx):
        return manejador.descargar_profundidad(ctx.identidad, ctx.ruta_params["render_id"])

    app.registrar("POST", RUTA_RENDER, _renderizar, PermisoCodigo.RENDERIZAR, "Renderizar escena en la escalera fotoreal")
    app.registrar("GET", RUTA_RENDERS, _listar, PermisoCodigo.VER, "Listar renders de la escena")
    app.registrar("GET", RUTA_IMAGEN, _descargar, PermisoCodigo.VER, "Descargar imagen del render")
    app.registrar("GET", RUTA_PROFUNDIDAD, _profundidad, PermisoCodigo.VER, "Descargar mapa de profundidad")
