"""Menu: Impuestos - NEXO / ZYRA.

Modulo finance. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "finance"
MENU_ID = "finance.impuestos"
TITLE = "Impuestos"
OPTIONS = ["Calcular", "Obligaciones", "Calendario"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
