"""Menu: Identidad Educativa - SEMILLA / ZYRA (SM8)."""
MODULE = "semilla"
MENU_ID = "modulo_1_identidad_educativa"
TITLE = "Identidad Educativa"
OPTIONS = ["Registro de estudiante", "Referencia ZID", "Verificacion de identidad"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
