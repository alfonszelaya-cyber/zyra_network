"""Salud e indice publicos de LABORATORIO (sin ZID)."""

from apps.laboratorio.schemas.responses.envelopes import exito

RUTA_SALUD = "/laboratorio/health"
RUTA_INDICE = "/laboratorio"

MIME_HTML = "text/html; charset=utf-8"

_PORTADA = "<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>LABORATORIO</title><style>body{font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;max-width:720px;margin:0 auto;padding:24px 16px}.mod{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:12px 14px;margin:8px 0}.mut{color:#8b949e}</style></head><body><div id='lab-portada'></div><h1>LABORATORIO</h1><p class='mut'>Experimentos, simulaciones y proyecciones dentro de ZYRA Network.</p><div class='mod'>Captura</div><div class='mod'>Creacion y Diseno</div><div class='mod'>Exportar y Biblioteca</div><div class='mod'>Presentar y Proyeccion</div><div class='mod'>Renderizar y Simulacion</div><div class='mod'>Comprension y Mundo 4D</div><p class='mut'>ZYRA Network</p></body></html>"


def registrar_rutas(app) -> None:
    estado_salud = app.contenedor.obtener("estado_salud")

    def _salud(ctx):
        return exito(estado_salud.estado())

    def _indice(ctx):
        return 200, _PORTADA.encode("utf-8"), {"Content-Type": MIME_HTML}

    app.registrar("GET", RUTA_SALUD, _salud, None,
                  "Estado de salud real", publica=True)
    app.registrar("GET", RUTA_INDICE, _indice, None,
                  "Indice de la aplicacion", publica=True)
