
"""Semilla Modules Router (SM8)."""
from __future__ import annotations
from apps.semilla.module import discover_menus

def list_menus(module="", limit=100) -> dict:
    """Lista de menus SEMILLA."""
    menus = discover_menus()
    if module:
        menus = [m for m in menus
                 if m.get("module") == module]
    return {"total": len(menus),
            "menus": menus[:limit]}

def get_menu(menu_id):
    """Un menu por id, o None."""
    for m in discover_menus():
        if m["menu_id"] == menu_id:
            return m
    return None
