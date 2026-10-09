"""Rutas API de presentaciones."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

RUTA_CREAR = "/laboratorio/api/v1/projects/{proyecto_id}/presentations"
RUTA_ITEM = "/laboratorio/api/v1/presentations/{presentacion_id}"
RUTA_PLAY = RUTA_ITEM + "/play"
RUTA_SELLAR = RUTA_ITEM + "/seal"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_presentaciones")

    def _crear(ctx):
        return manejador.crear(ctx.identidad, ctx.ruta_params["proyecto_id"], ctx.json())

    def _listar(ctx):
        return manejador.listar(ctx.identidad, ctx.ruta_params["proyecto_id"])

    def _obtener(ctx):
        return manejador.obtener(ctx.identidad, ctx.ruta_params["presentacion_id"])

    def _reproducir(ctx):
        return manejador.reproducir(ctx.identidad, ctx.ruta_params["presentacion_id"])

    def _sellar(ctx):
        return manejador.sellar(ctx.identidad, ctx.ruta_params["presentacion_id"])

    app.registrar("POST", RUTA_CREAR, _crear, PermisoCodigo.PRESENTAR, "Crear presentacion con pasos")
    app.registrar("GET", RUTA_CREAR, _listar, PermisoCodigo.VER, "Listar presentaciones")
    app.registrar("GET", RUTA_ITEM, _obtener, PermisoCodigo.VER, "Obtener presentacion")
    app.registrar("GET", RUTA_PLAY, _reproducir, PermisoCodigo.VER, "Reproducir slideshow real")
    app.registrar("POST", RUTA_SELLAR, _sellar, PermisoCodigo.PRESENTAR, "Sellar en ZYRA via outbox")
