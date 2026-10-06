"""Menu: Alertas - NEXO / ZYRA.

Modulo executive. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "executive"
MENU_ID = "executive.inteligencia_zyra.alertas"
TITLE = "Alertas"
OPTIONS = ["Ver alertas"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
