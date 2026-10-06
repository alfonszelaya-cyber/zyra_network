
"""Nexo Modules Router - menus como data para
HTTP (NG10). El wiring a server.py ocurre en
NG12 con audit-first."""
from __future__ import annotations
from apps.nexo.module import discover_menus

def list_menus(module="", limit=500) -> dict:
    """Lista de menus por modulo o todos."""
    menus = discover_menus()
    if module:
        menus = [m for m in menus
                 if m["module"] == module]
    return {"total": len(menus),
            "menus": menus[:limit]}

def get_menu(menu_id):
    """Un menu por id, o None."""
    for m in discover_menus():
        if m["menu_id"] == menu_id:
            return m
    return None
