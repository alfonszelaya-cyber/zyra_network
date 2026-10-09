"""Registro unico de rutas HTTP (metodo, patron, handler, permiso)."""
import re

METODOS = ("GET", "POST", "PUT", "PATCH", "DELETE")


class RegistroRutas:
    def __init__(self):
        self._rutas = []

    def registrar(self, metodo: str, patron: str, handler, permiso: str = None, descripcion: str = "", publica: bool = False) -> None:
        metodo = str(metodo).upper()
        if metodo not in METODOS:
            raise ValueError("Metodo HTTP no soportado: " + metodo)
        if not isinstance(patron, str) or not patron.startswith("/"):
            raise ValueError("Patron de ruta debe iniciar con /: " + repr(patron))
        if not callable(handler):
            raise ValueError("El handler debe ser callable.")
        for ruta in self._rutas:
            if ruta["metodo"] == metodo and ruta["patron"] == patron:
                raise ValueError("Ruta duplicada: " + metodo + " " + patron)
        regex = re.compile(
            "^" + re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", r"(?P<\1>[^/]+)", patron) + "$"
        )
        self._rutas.append({
            "metodo": metodo, "patron": patron, "regex": regex,
            "handler": handler, "permiso": permiso,
            "descripcion": descripcion, "publica": bool(publica),
        })

    def resolver(self, metodo: str, ruta: str):
        metodo = str(metodo).upper()
        ruta = "/" + ruta.strip("/") if ruta.strip() else "/"
        for entrada in self._rutas:
            coincidencia = entrada["regex"].match(ruta)
            if coincidencia and entrada["metodo"] == metodo:
                return (
                    entrada["handler"],
                    coincidencia.groupdict(),
                    entrada["permiso"],
                    entrada["publica"],
                )
        return None, None, None, False

    def listar(self) -> list:
        return [
            {"metodo": r["metodo"], "patron": r["patron"], "permiso": r["permiso"], "descripcion": r["descripcion"]}
            for r in self._rutas
        ]

    def total(self) -> int:
        return len(self._rutas)
