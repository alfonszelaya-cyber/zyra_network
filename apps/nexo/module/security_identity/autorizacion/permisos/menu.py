"""Menu: Permisos - NEXO / ZYRA.

Modulo security_identity. Opciones reales del
ecosistema NEXO; wiring de acciones en NG12.
"""
MODULE = "security_identity"
MENU_ID = "security_identity.autorizacion.permisos"
TITLE = "Permisos"
OPTIONS = ["Otorgar", "Revocar", "Verificar"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
