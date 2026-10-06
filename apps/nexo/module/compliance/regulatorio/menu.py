"""Menu: Regulatorio - NEXO / ZYRA.

Modulo compliance. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "compliance"
MENU_ID = "compliance.regulatorio"
TITLE = "Regulatorio"
OPTIONS = ["Ver requisitos", "Verificar cumplimiento"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
