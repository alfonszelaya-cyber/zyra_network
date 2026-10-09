"""Acceso a roles con validacion cruzada contra el arbol de menus."""

from apps.laboratorio.permissions.roles.role_definitions import (
    DEFINICIONES,
    definicion,
)
from apps.laboratorio.registry.menus.menu_tree import existe as existe_menu


def descripcion(rol: str) -> dict:
    return definicion(rol)


def menus_de(rol: str) -> tuple:
    menus = definicion(rol)["menus"]
    for id_menu in menus:
        if not existe_menu(id_menu):
            raise ValueError(
                "El rol " + rol + " referencia un menu inexistente: " + id_menu
            )
    return menus


def todos() -> list:
    return [
        {
            "rol": rol,
            "nombre": d["nombre"],
            "descripcion": d["descripcion"],
            "menus": list(d["menus"]),
        }
        for rol, d in DEFINICIONES.items()
    ]
