"""Rutas API de destinos de salida."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

RUTA_DISPLAYS = "/laboratorio/api/v1/displays"
RUTA_TEST = RUTA_DISPLAYS + "/{salida_id}/test"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_salidas")

    def _registrar(ctx):
        return manejador.registrar(ctx.identidad, ctx.json())

    def _listar(ctx):
        return manejador.listar(ctx.identidad)

    def _probar(ctx):
        return manejador.probar(ctx.identidad, ctx.ruta_params["salida_id"])

    app.registrar("POST", RUTA_DISPLAYS, _registrar, PermisoCodigo.PROYECTAR, "Registrar destino de salida")
    app.registrar("GET", RUTA_DISPLAYS, _listar, PermisoCodigo.VER, "Listar salidas")
    app.registrar("POST", RUTA_TEST, _probar, PermisoCodigo.PROYECTAR, "Probar salida con patron real")
