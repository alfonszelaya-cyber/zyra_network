"""Rutas API de escenas 3D y generacion de artefactos."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

PREFIJO = "/laboratorio/api/v1/projects/{proyecto_id}/scenes"
RUTA_ESCENA = "/laboratorio/api/v1/scenes/{escena_id}"
RUTA_GENERAR = RUTA_ESCENA + "/generate"
RUTA_ART = "/laboratorio/api/v1/artifacts/{artefacto_id}"
RUTA_ARTS = "/laboratorio/api/v1/projects/{proyecto_id}/artifacts"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_creacion")

    def _crear(ctx):
        return manejador.crear_escena(ctx.identidad, ctx.ruta_params["proyecto_id"], ctx.json())

    def _listar(ctx):
        return manejador.listar_escenas(ctx.identidad, ctx.ruta_params["proyecto_id"])

    def _obtener(ctx):
        return manejador.obtener_escena(ctx.identidad, ctx.ruta_params["escena_id"])

    def _generar(ctx):
        return manejador.generar(ctx.identidad, ctx.ruta_params["escena_id"], ctx.json())

    def _artefactos(ctx):
        return manejador.listar_artefactos(ctx.identidad, ctx.ruta_params["proyecto_id"])

    def _descargar(ctx):
        return manejador.descargar_artefacto(ctx.identidad, ctx.ruta_params["artefacto_id"])

    app.registrar("POST", PREFIJO, _crear, PermisoCodigo.CREAR_CONTENIDO, "Crear escena 3D")
    app.registrar("GET", PREFIJO, _listar, PermisoCodigo.VER, "Listar escenas del proyecto")
    app.registrar("GET", RUTA_ESCENA, _obtener, PermisoCodigo.VER, "Obtener escena")
    app.registrar("POST", RUTA_GENERAR, _generar, PermisoCodigo.CREAR_CONTENIDO, "Generar artefacto")
    app.registrar("GET", RUTA_ARTS, _artefactos, PermisoCodigo.VER, "Listar artefactos del proyecto")
    app.registrar("GET", RUTA_ART, _descargar, PermisoCodigo.VER, "Descargar artefacto")
