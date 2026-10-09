"""Salud e indice publicos de LABORATORIO (sin ZID)."""

from apps.laboratorio.schemas.responses.envelopes import exito

RUTA_SALUD = "/laboratorio/health"
RUTA_INDICE = "/laboratorio"


def registrar_rutas(app) -> None:
    estado_salud = app.contenedor.obtener("estado_salud")

    def _salud(ctx):
        return exito(estado_salud.estado())

    def _indice(ctx):
        return exito({
            "app": "laboratorio",
            "nombre": "ZYRA LABORATORIO",
            "mensaje": "LABORATORIO activo dentro de ZYRA Network",
            "rutas": app.listar_rutas(),
            "modulos": app.contenedor.obtener("registro_modulos").listar(),
        })

    app.registrar("GET", RUTA_SALUD, _salud, None, "Estado de salud real", publica=True)
    app.registrar("GET", RUTA_INDICE, _indice, None, "Indice de la aplicacion", publica=True)
