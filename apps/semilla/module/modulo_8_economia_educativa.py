"""Menu: Economia Educativa - SEMILLA / ZYRA (SM8)."""
MODULE = "semilla"
MENU_ID = "modulo_8_economia_educativa"
TITLE = "Economia Educativa"
OPTIONS = ["Becas", "Pagos escolares", "Subsidios y bonos"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
