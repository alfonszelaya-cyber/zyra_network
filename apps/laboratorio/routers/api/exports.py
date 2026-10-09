"""Rutas API de exportaciones."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

RUTA_CREAR = "/laboratorio/api/v1/projects/{proyecto_id}/exports"
RUTA_ITEM = "/laboratorio/api/v1/exports/{export_id}"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_exportaciones")

    def _crear(ctx):
        return manejador.crear(ctx.identidad, ctx.ruta_params["proyecto_id"], ctx.json())

    def _listar(ctx):
        return manejador.listar(ctx.identidad, ctx.ruta_params["proyecto_id"])

    def _obtener(ctx):
        return manejador.obtener(ctx.identidad, ctx.ruta_params["export_id"])

    app.registrar("POST", RUTA_CREAR, _crear, PermisoCodigo.EXPORTAR, "Exportar bundle o enviar a ZYRA")
    app.registrar("GET", RUTA_CREAR, _listar, PermisoCodigo.VER, "Listar exportaciones")
    app.registrar("GET", RUTA_ITEM, _obtener, PermisoCodigo.VER, "Obtener exportacion")
