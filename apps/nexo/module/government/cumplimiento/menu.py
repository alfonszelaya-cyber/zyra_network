"""Menu: Cumplimiento - NEXO / ZYRA.

Modulo government. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "government"
MENU_ID = "government.cumplimiento"
TITLE = "Cumplimiento"
OPTIONS = ["Requisitos", "Tasa de cumplimiento"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
