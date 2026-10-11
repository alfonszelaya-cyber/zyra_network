"""Rutas internas de LABORATORIO: feed de eventos y cache.

El feed permite a navegadores y moviles obtener eventos en vivo
por cursor (polling eficiente, sin instalar nada).
"""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo
from apps.laboratorio.schemas.responses.envelopes import exito

RUTA_EVENTOS = "/laboratorio/api/v1/events"
RUTA_CACHE_STATS = "/laboratorio/api/v1/cache/stats"


def registrar_rutas_internas(app) -> None:
    colector = app.contenedor.obtener("colector_eventos")
    cache = app.contenedor.obtener("cache_global")

    def _eventos(ctx):
        desde = ctx.query.get("desde", "0")
        limite = ctx.query.get("limite", "50")
        try:
            desde_num = int(desde)
        except ValueError:
            desde_num = 0
        try:
            limite_num = int(limite)
        except ValueError:
            limite_num = 50
        return exito(colector.historial(desde_num, limite_num))

    def _cache(ctx):
        return exito(cache.estadisticas())

    app.registrar(
        "GET", RUTA_EVENTOS, _eventos,
        PermisoCodigo.VER,
        "Feed de eventos en vivo con cursor (polling)",
    )
    app.registrar(
        "GET", RUTA_CACHE_STATS, _cache,
        PermisoCodigo.VER,
        "Estadisticas reales de la cache TTL",
    )
