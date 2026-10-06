"""Menu: Actividad - NEXO / ZYRA.

Modulo executive. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "executive"
MENU_ID = "executive.panel_principal.actividad"
TITLE = "Actividad"
OPTIONS = ["Ver actividad reciente"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
