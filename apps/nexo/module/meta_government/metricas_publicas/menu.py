"""Menu: Metricas Publicas - NEXO / ZYRA.

Modulo meta_government. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "meta_government"
MENU_ID = "meta_government.metricas_publicas"
TITLE = "Metricas Publicas"
OPTIONS = ["Publicar", "Consultar"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
