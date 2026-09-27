"""AGRO - navegacion del modulo insumos_y_apoyos."""
MENU = {
    "key": "insumos_y_apoyos",
    "title": "Insumos y Apoyos",
    "items": [{'label': 'Apoyos entregados', 'path': '/agro/gobierno/beneficiados'}],
}


def menu():
    return dict(MENU)
