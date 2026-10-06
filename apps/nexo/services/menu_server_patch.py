
"""Menu server patch - aditivo (regla 51)."""
from __future__ import annotations
import json as _json
from apps.nexo.routers.modules_router import (
    list_menus, get_menu)

def apply_menu_routes(handler_cls):
    """Aplica el patch una sola vez."""
    if getattr(handler_cls,
               "_ng12_menus_applied", False):
        return handler_cls
    original = getattr(handler_cls, "do_GET",
                       None)

    def do_GET(self):
        path = ((getattr(self, "path", "")
                 or "").split("?")[0])
        if (path == "/nexo/menus"
                or path.startswith(
                    "/nexo/menus/")):
            mid = ""
            if len(path) > len("/nexo/menus/"):
                mid = path[len("/nexo/menus/"):]\
                    .lstrip("/")
            if mid:
                m = get_menu(mid)
                code = 200 if m else 404
                payload = (m if m else
                           {"error": "menu no"
                                     " encontrado"})
            else:
                code = 200
                payload = list_menus()
            body = _json.dumps(
                payload,
                default=str).encode("utf-8")
            self.send_response(code)
            self.send_header(
                "Content-Type",
                "application/json")
            self.send_header(
                "Content-Length",
                str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if original is not None:
            return original(self)
        self.send_response(404)
        self.end_headers()

    handler_cls.do_GET = do_GET
    handler_cls._ng12_menus_applied = True
    return handler_cls
