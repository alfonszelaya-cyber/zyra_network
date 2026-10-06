"""Menu: Contabilidad - NEXO / ZYRA.

Modulo accounting. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "accounting"
MENU_ID = "accounting"
TITLE = "Contabilidad"
OPTIONS = ["Resumen contable", "Libro diario", "Libro mayor", "Balances", "Cierres"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
