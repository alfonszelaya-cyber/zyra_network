"""Menu: Indicadores (KPIs) - NEXO / ZYRA.

Modulo executive. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "executive"
MENU_ID = "executive.indicadores"
TITLE = "Indicadores (KPIs)"
OPTIONS = ["Ver KPIs"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
