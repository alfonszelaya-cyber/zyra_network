"""Rutas API de proyectos."""

from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

PREFIJO = "/laboratorio/api/v1/projects"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_proyectos")

    def _crear(ctx):
        return manejador.crear(ctx.identidad, ctx.json())

    def _listar(ctx):
        return manejador.listar(ctx.identidad, ctx.query)

    def _obtener(ctx):
        return manejador.obtener(ctx.identidad, ctx.ruta_params["proyecto_id"])

    app.registrar("POST", PREFIJO, _crear, PermisoCodigo.PROYECTO_CREAR, "Crear proyecto")
    app.registrar("GET", PREFIJO, _listar, PermisoCodigo.VER, "Listar mis proyectos")
    app.registrar("GET", PREFIJO + "/{proyecto_id}", _obtener, PermisoCodigo.VER, "Obtener proyecto")
