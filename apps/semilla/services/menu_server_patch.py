
"""Menu server patch SEMILLA - aditivo (regla 51,
SE-1 intacto). Idempotente."""
from __future__ import annotations
import json as _json
from apps.semilla.module import discover_menus

def apply_menu_routes(handler_cls):
    """Aplica el patch una sola vez."""
    if getattr(handler_cls,
               "_sm8_menus_applied", False):
        return handler_cls
    original = getattr(handler_cls, "do_GET",
                       None)

    def do_GET(self):
        path = ((getattr(self, "path", "")
                 or "").split("?")[0])
        if (path == "/semilla/menus"
                or path.startswith(
                    "/semilla/menus/")):
            mid = ""
            if len(path) > len(
                    "/semilla/menus/"):
                mid = path[len("/semilla/menus/"):]\
                    .lstrip("/")
            found = None
            for m in discover_menus():
                if m["menu_id"] == mid:
                    found = m
                    break
            if mid:
                code = 200 if found else 404
                payload = (found if found else
                           {"error": "menu no"
                                     " encontrado"})
            else:
                code = 200
                payload = {"total":
                           len(discover_menus()),
                           "menus":
                           discover_menus()}
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
    handler_cls._sm8_menus_applied = True
    return handler_cls
