"""Menu: Coordinacion Institucional - NEXO / ZYRA.

Modulo meta_government. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "meta_government"
MENU_ID = "meta_government.coordinacion"
TITLE = "Coordinacion Institucional"
OPTIONS = ["Proponer acuerdo", "Ver activos"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
