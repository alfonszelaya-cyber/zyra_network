"""Verificacion de integridad de las plantillas HTML de UI."""

from apps.laboratorio.application.services.ui_service import cargar_plantilla

PLANTILLAS_OFICIALES = (
    "base.html", "home.html", "panel.html", "crear.html",
    "capturar.html", "comprender.html", "disenar.html",
)


def verificar_plantillas() -> int:
    """Valida que las 7 plantillas existan y sean legibles."""
    total = 0
    for nombre in PLANTILLAS_OFICIALES:
        cargar_plantilla(nombre)
        total += 1
    return total
