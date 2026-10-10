"""Rutas API de superficies y proyeccion en vivo."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

RUTA_SURFACES = "/laboratorio/api/v1/surfaces"
RUTA_CALIBRAR = RUTA_SURFACES + "/{superficie_id}/calibrate"
RUTA_PROYECTAR = "/laboratorio/api/v1/scenes/{escena_id}/project"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_proyeccion")

    def _registrar(ctx):
        return manejador.registrar(ctx.identidad, ctx.json())

    def _listar(ctx):
        return manejador.listar(ctx.identidad)

    def _calibrar(ctx):
        return manejador.calibrar(ctx.identidad, ctx.ruta_params["superficie_id"], ctx.json())

    def _proyectar(ctx):
        return manejador.proyectar(ctx.identidad, ctx.ruta_params["escena_id"], ctx.json())

    app.registrar("POST", RUTA_SURFACES, _registrar, PermisoCodigo.PROYECTAR, "Registrar superficie")
    app.registrar("GET", RUTA_SURFACES, _listar, PermisoCodigo.VER, "Listar mis superficies")
    app.registrar("POST", RUTA_CALIBRAR, _calibrar, PermisoCodigo.PROYECTAR, "Calibrar con 4 esquinas")
    app.registrar("POST", RUTA_PROYECTAR, _proyectar, PermisoCodigo.PROYECTAR, "Proyectar escena en superficie")
