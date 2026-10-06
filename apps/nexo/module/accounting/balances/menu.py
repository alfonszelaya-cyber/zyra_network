"""Menu: Balances - NEXO / ZYRA.

Modulo accounting. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "accounting"
MENU_ID = "accounting.balances"
TITLE = "Balances"
OPTIONS = ["Balance de comprobacion", "Balance general"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
