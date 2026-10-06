"""Menu: Riesgo Geopolitico - NEXO / ZYRA.

Modulo risk. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "risk"
MENU_ID = "risk.geopolitico"
TITLE = "Riesgo Geopolitico"
OPTIONS = ["Evaluar"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
