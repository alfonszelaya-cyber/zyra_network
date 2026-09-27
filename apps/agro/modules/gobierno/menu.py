"""AGRO - navegacion del modulo gobierno."""
MENU = {
    "key": "gobierno",
    "title": "Gobierno",
    "items": [{'label': 'Panel general', 'path': '/agro/gobierno'}, {'label': 'Seguridad alimentaria', 'path': '/agro/gobierno/seguridad'}, {'label': 'Beneficiados', 'path': '/agro/gobierno/beneficiados'}, {'label': 'Riesgos', 'path': '/agro/gobierno/riesgos'}],
}


def menu():
    return dict(MENU)
