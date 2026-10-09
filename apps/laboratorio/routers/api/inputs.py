"""Rutas API de entradas de captura y comprension."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

PREFIJO = "/laboratorio/api/v1/projects/{proyecto_id}/inputs"
RUTA_ENTRADA = "/laboratorio/api/v1/inputs/{entrada_id}"
RUTA_ENTENDER = RUTA_ENTRADA + "/understand"


def registrar_rutas(app) -> None:
    capturas = app.contenedor.obtener("manejador_capturas")
    comprension = app.contenedor.obtener("manejador_comprension")

    def _crear(ctx):
        return capturas.crear(ctx.identidad, ctx.ruta_params["proyecto_id"], ctx.json())

    def _listar(ctx):
        return capturas.listar(ctx.identidad, ctx.ruta_params["proyecto_id"])

    def _obtener(ctx):
        return capturas.obtener(ctx.identidad, ctx.ruta_params["entrada_id"])

    def _entender(ctx):
        return comprension.comprender(ctx.identidad, ctx.ruta_params["entrada_id"])

    def _comprension(ctx):
        return comprension.obtener(ctx.identidad, ctx.ruta_params["entrada_id"])

    app.registrar("POST", PREFIJO, _crear, PermisoCodigo.CAPTURAR, "Capturar entrada")
    app.registrar("GET", PREFIJO, _listar, PermisoCodigo.VER, "Listar entradas del proyecto")
    app.registrar("GET", RUTA_ENTRADA, _obtener, PermisoCodigo.VER, "Obtener entrada")
    app.registrar("POST", RUTA_ENTENDER, _entender, PermisoCodigo.CAPTURAR, "Comprender entrada (motor real)")
    app.registrar("GET", RUTA_ENTENDER, _comprension, PermisoCodigo.VER, "Comprension de la entrada")
