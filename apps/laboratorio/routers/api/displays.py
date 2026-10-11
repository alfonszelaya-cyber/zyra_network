"""Rutas API de salidas: registro clasico + destinos universales.

Los destinos universales aceptan cualquier dispositivo sin
codigo nuevo: pantalla_local, hdmi, proyector, udp, web,
hypervsn, looking_glass, openxr, auto.
"""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo
from apps.laboratorio.shared.exceptions.domain_errors import (
    EntidadNoEncontradaError,
)

RUTA_DISPLAYS = "/laboratorio/api/v1/displays"
RUTA_TEST = RUTA_DISPLAYS + "/{salida_id}/test"
RUTA_TARGETS = RUTA_DISPLAYS + "/targets"
RUTA_TARGET = RUTA_TARGETS + "/{salida_id}"
RUTA_FRAME = RUTA_TARGET + "/frame"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_salidas")
    universales = app.contenedor.obtener("salidas_universales")

    def _registrar(ctx):
        return manejador.registrar(ctx.identidad, ctx.json())

    def _listar(ctx):
        return manejador.listar(ctx.identidad)

    def _probar(ctx):
        return manejador.probar(
            ctx.identidad, ctx.ruta_params["salida_id"]
        )

    def _registrar_destino(ctx):
        datos = ctx.json()
        tipo = str(datos.get("tipo", "web")).strip()
        direccion = str(datos.get("direccion", "")).strip()
        nombre = str(datos.get("nombre", "")).strip()
        return universales.registrar_destino(tipo, direccion, nombre)

    def _listar_destinos(ctx):
        return universales.listar_destinos()

    def _quitar_destino(ctx):
        salida_id = ctx.ruta_params["salida_id"]
        eliminado = universales.quitar_destino(salida_id)
        if not eliminado:
            raise EntidadNoEncontradaError(
                "Destino inexistente.", salida_id
            )
        return {"eliminado": True, "id": salida_id}

    def _frame(ctx):
        salida_id = ctx.ruta_params["salida_id"]
        try:
            frame, mime = universales.frame_actual(salida_id)
        except ValueError as exc:
            raise EntidadNoEncontradaError(str(exc), salida_id)
        return 200, frame, {
            "Content-Type": mime,
            "Cache-Control": "no-store",
        }

    app.registrar(
        "POST", RUTA_DISPLAYS, _registrar,
        PermisoCodigo.PROYECTAR, "Registrar destino de salida",
    )
    app.registrar(
        "GET", RUTA_DISPLAYS, _listar,
        PermisoCodigo.VER, "Listar salidas",
    )
    app.registrar(
        "POST", RUTA_TEST, _probar,
        PermisoCodigo.PROYECTAR, "Probar salida con patron real",
    )
    app.registrar(
        "POST", RUTA_TARGETS, _registrar_destino,
        PermisoCodigo.PROYECTAR,
        "Registrar destino universal en caliente",
    )
    app.registrar(
        "GET", RUTA_TARGETS, _listar_destinos,
        PermisoCodigo.VER,
        "Listar destinos universales y deteccion",
    )
    app.registrar(
        "DELETE", RUTA_TARGET, _quitar_destino,
        PermisoCodigo.PROYECTAR, "Quitar destino universal",
    )
    app.registrar(
        "GET", RUTA_FRAME, _frame,
        PermisoCodigo.VER,
        "Frame actual (pull para telefonos y navegadores)",
    )
