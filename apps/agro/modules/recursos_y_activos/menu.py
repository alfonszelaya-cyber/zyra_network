"""AGRO - navegacion del modulo recursos_y_activos."""
MENU = {
    "key": "recursos_y_activos",
    "title": "Recursos y Activos",
    "items": [{'label': 'Tierras y maquinaria', 'path': '/agro/gobierno'}],
}


def menu():
    return dict(MENU)
