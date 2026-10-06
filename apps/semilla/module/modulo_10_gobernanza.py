"""Menu: Gobernanza - SEMILLA / ZYRA (SM8)."""
MODULE = "semilla"
MENU_ID = "modulo_10_gobernanza"
TITLE = "Gobernanza"
OPTIONS = ["Supervision escolar", "Panel ministerial", "Reportes"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
