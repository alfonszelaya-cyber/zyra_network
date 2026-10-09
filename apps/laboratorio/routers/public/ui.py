"""Rutas de la interfaz HTML de LABORATORIO (dashboard por rol)."""
from pathlib import Path

from apps.laboratorio.application.services import ui_service
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError

MIME_HTML = "text/html; charset=utf-8"
RAIZ_ASSETS = Path(__file__).resolve().parents[2] / "assets"

ASSETS = {
    "logo.svg": ("logos/zyra_lab.svg", "image/svg+xml"),
    "icons.svg": ("icons/ui_icons.svg", "image/svg+xml"),
    "tokens.json": ("templates/ui_tokens.json", "application/json"),
    "es.json": ("translations/es.json", "application/json"),
}


def _html(status: int, texto: str) -> tuple:
    return status, texto.encode("utf-8"), {
        "Content-Type": MIME_HTML,
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
    }


def registrar_rutas(app) -> None:
    repos = {
        "proyectos": app.contenedor.obtener("repo_proyectos"),
        "escenarios": app.contenedor.obtener("repo_escenarios"),
        "inputs": app.contenedor.obtener("repo_inputs"),
        "comprensiones": app.contenedor.obtener("repo_comprensiones"),
        "disenos": app.contenedor.obtener("repo_disenos"),
        "escenas": app.contenedor.obtener("repo_escenas"),
        "artefactos": app.contenedor.obtener("repo_artefactos"),
        "activos": app.contenedor.obtener("repo_activos"),
    }

    def _home(ctx):
        return _html(200, ui_service.render_home(ctx.identidad, repos["proyectos"]))

    def _panel(ctx):
        return _html(200, ui_service.render_panel(
            ctx.identidad, ctx.ruta_params["menu_id"], ctx.query.get("sub", ""), repos,
        ))

    def _asset(ctx):
        nombre = ctx.ruta_params["nombre"]
        if nombre not in ASSETS:
            raise EntidadNoEncontradaError("Asset inexistente.", nombre)
        relativa, mime = ASSETS[nombre]
        ruta = RAIZ_ASSETS / relativa
        if not ruta.is_file():
            raise EntidadNoEncontradaError("Asset ausente en disco.", nombre)
        datos = ruta.read_bytes()
        return 200, datos, {
            "Content-Type": mime,
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        }

    app.registrar("GET", "/laboratorio/ui", _home, PermisoCodigo.VER, "Inicio UI")
    app.registrar("GET", "/laboratorio/ui/assets/{nombre}", _asset, PermisoCodigo.VER, "Assets de UI")
    app.registrar("GET", "/laboratorio/ui/{menu_id}", _panel, PermisoCodigo.VER, "Panel por menu")
