"""Motor de render SVG: calidad BORRADOR real y honesto."""

import re

from apps.laboratorio.shared.adapters.engine_adapter import AdaptadorMotor
from apps.laboratorio.shared.exceptions.render_errors import (
    EscenaVaciaError,
    RenderFallidoError,
)
from apps.laboratorio.shared.interfaces.renderer import Renderer, ResultadoRender
from apps.laboratorio.infrastructure.security.html_sanitizer import escapar

PATRON_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
PCT = chr(37)


def _n(valor) -> str:
    numero = float(valor)
    if numero != numero or numero in (float("inf"), float("-inf")):
        raise RenderFallidoError("Coordenada no finita.")
    return "%.2f" % numero


class MotorRenderSVG(AdaptadorMotor, Renderer):
    def __init__(self):
        AdaptadorMotor.__init__(self, "renderer_svg", "renderer", "1.0.0")
        self.marcar_disponible()

    def capacidades(self) -> dict:
        return {
            "calidades": ["borrador"],
            "profundidad": False,
            "formato": "svg",
            "nota": "Canal de profundidad se activa con el motor 3D (fase 6).",
        }

    def renderizar(self, escena, opciones) -> ResultadoRender:
        if not isinstance(escena, dict):
            raise RenderFallidoError("La escena debe ser un dict de especificacion.")
        objetos = escena.get("objetos", [])
        if not objetos:
            raise EscenaVaciaError("La escena no tiene objetos que renderizar.")
        ancho = int(escena.get("ancho", 800))
        alto = int(escena.get("alto", 600))
        if not 16 <= ancho <= 4096 or not 16 <= alto <= 4096:
            raise RenderFallidoError("Dimensiones fuera de rango 16-4096.")
        fondo = str(escena.get("fondo", "#0F172A"))
        if not PATRON_HEX.match(fondo):
            raise RenderFallidoError("Color de fondo invalido: " + fondo)
        rect_fondo = '<rect width="100' + PCT + '" height="100' + PCT + '" fill="' + fondo + '"/>'
        partes = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (ancho, alto, ancho, alto),
            rect_fondo,
        ]
        for objeto in objetos:
            partes.append(self._objeto(objeto))
        partes.append('</svg>')
        svg = "\n".join(partes).encode("utf-8")
        return ResultadoRender(
            imagen_bytes=svg,
            profundidad_bytes=None,
            ancho=ancho,
            alto=alto,
            metadata={"formato": "svg", "motor": "renderer_svg", "objetos": len(objetos)},
        )

    def _objeto(self, objeto) -> str:
        if not isinstance(objeto, dict):
            raise RenderFallidoError("Objeto invalido.")
        forma = str(objeto.get("forma", "")).lower()
        color = str(objeto.get("color", "#64748B"))
        if not PATRON_HEX.match(color):
            raise RenderFallidoError("Color de objeto invalido: " + color)
        if forma == "rect":
            return '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % (
                _n(objeto.get("x", 0)), _n(objeto.get("y", 0)),
                _n(objeto.get("w", 10)), _n(objeto.get("h", 10)), color)
        if forma == "circle":
            return '<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (
                _n(objeto.get("cx", 0)), _n(objeto.get("cy", 0)),
                _n(objeto.get("r", 10)), color)
        if forma == "texto":
            return '<text x="%s" y="%s" fill="%s" font-size="%s" font-family="sans-serif">%s</text>' % (
                _n(objeto.get("x", 0)), _n(objeto.get("y", 20)), color,
                _n(objeto.get("tamano", 14)), escapar(objeto.get("contenido", "")))
        raise RenderFallidoError("Forma no soportada por renderer SVG: " + forma)
