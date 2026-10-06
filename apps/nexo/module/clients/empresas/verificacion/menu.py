"""Menu: Verificacion de Empresa - NEXO / ZYRA.

Modulo clients. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "clients"
MENU_ID = "clients.empresas.verificacion"
TITLE = "Verificacion de Empresa"
OPTIONS = ["Verificar datos"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
