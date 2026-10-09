"""Rutas API de documentos: previsualizar y crear proyecto desde texto."""

from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

RUTA_PREVIA = "/laboratorio/api/v1/parse-document"
RUTA_CREAR = "/laboratorio/api/v1/documents/create-project"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_documentos")

    def _previa(ctx):
        return manejador.previsualizar(ctx.identidad, ctx.json())

    def _crear(ctx):
        return manejador.crear_proyecto(ctx.identidad, ctx.json())

    app.registrar("POST", RUTA_PREVIA, _previa, PermisoCodigo.CAPTURAR, "Previsualizar parseo de documento")
    app.registrar("POST", RUTA_CREAR, _crear, PermisoCodigo.PROYECTO_CREAR, "Crear proyecto desde documento")
