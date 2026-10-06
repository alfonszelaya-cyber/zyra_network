"""Menu: Panel Financiero - NEXO / ZYRA.

Modulo finance. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "finance"
MENU_ID = "finance.panel_financiero"
TITLE = "Panel Financiero"
OPTIONS = ["Ver panel"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
