"""Menu: Reportes de Servicio - NEXO / ZYRA.

Modulo customer_service. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "customer_service"
MENU_ID = "customer_service.reportes"
TITLE = "Reportes de Servicio"
OPTIONS = ["Reporte de servicio"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
