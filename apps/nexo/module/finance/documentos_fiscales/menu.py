"""Menu: Documentos Fiscales - NEXO / ZYRA.

Modulo finance. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "finance"
MENU_ID = "finance.documentos_fiscales"
TITLE = "Documentos Fiscales"
OPTIONS = ["Registrar", "Consultar"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
