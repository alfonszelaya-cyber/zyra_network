"""Menu: Flujo de Proceso - NEXO / ZYRA.

Modulo operaciones. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "operaciones"
MENU_ID = "operaciones.procesos.flujo"
TITLE = "Flujo de Proceso"
OPTIONS = ["Ver timeline"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
