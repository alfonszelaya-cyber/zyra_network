"""Menu: Rendicion de Cuentas - NEXO / ZYRA.

Modulo government. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "government"
MENU_ID = "government.reportes"
TITLE = "Rendicion de Cuentas"
OPTIONS = ["Generar reporte"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
