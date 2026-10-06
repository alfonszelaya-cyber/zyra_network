"""Menu: Metricas Operativas - NEXO / ZYRA.

Modulo operaciones. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "operaciones"
MENU_ID = "operaciones.metricas"
TITLE = "Metricas Operativas"
OPTIONS = ["Calcular periodo", "Ver historico"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
