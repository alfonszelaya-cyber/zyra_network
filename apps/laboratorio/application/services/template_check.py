"""Verificacion de integridad de las plantillas HTML de UI."""

from apps.laboratorio.application.services.ui_service import cargar_plantilla


def verificar_plantillas() -> int:
    """Valida que las 4 plantillas existan y sean legibles."""
    total = 0
    for nombre in ("base.html", "home.html", "panel.html", "crear.html"):
        cargar_plantilla(nombre)
        total += 1
    return total
