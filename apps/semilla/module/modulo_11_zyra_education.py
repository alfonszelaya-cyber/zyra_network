"""Menu: ZYRA Education - SEMILLA / ZYRA (SM8)."""
MODULE = "semilla"
MENU_ID = "modulo_11_zyra_education"
TITLE = "ZYRA Education"
OPTIONS = ["Credenciales educativas", "Historial en la Red", "Eventos SEMILLA"]


def menu() -> dict:
    """Definicion del menu (data puro)."""
    return {"module": MODULE,
            "menu_id": MENU_ID,
            "title": TITLE,
            "options": [{"key": str(i + 1),
                         "label": opt}
                        for i, opt
                        in enumerate(OPTIONS)]}
