"""Rutas API de la biblioteca de activos."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

RUTA_ASSETS = "/laboratorio/api/v1/assets"
RUTA_BUSCAR = RUTA_ASSETS + "/search"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_biblioteca")

    def _crear(ctx):
        return manejador.crear(ctx.identidad, ctx.json())

    def _listar(ctx):
        return manejador.listar(ctx.identidad)

    def _buscar(ctx):
        return manejador.buscar(ctx.identidad, ctx.query.get("etiqueta", ""))

    app.registrar("POST", RUTA_ASSETS, _crear, PermisoCodigo.BIBLIOTECA_GESTIONAR, "Guardar activo")
    app.registrar("GET", RUTA_ASSETS, _listar, PermisoCodigo.VER, "Listar mis activos")
    app.registrar("GET", RUTA_BUSCAR, _buscar, PermisoCodigo.VER, "Buscar activos por etiqueta")
