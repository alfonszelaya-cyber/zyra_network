"""Menu: Gobierno Familiar - NEXO / ZYRA.

Modulo family_office. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "family_office"
MENU_ID = "family_office.gobierno_familiar"
TITLE = "Gobierno Familiar"
OPTIONS = ["Registrar decision", "Ver decisiones"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
