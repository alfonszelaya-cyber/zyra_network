"""Motor NAKED-3D: el efecto de las pantallas 3D sin lentes.

Genera un SVG con marco de pantalla y 3 capas de profundidad que
se desplazan en contrafase (parallax): el frente sale del marco,
el fondo queda fijo. Es el mismo principio de las vallas 3D de
China adaptado a SVG animado real.
"""
from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.shared.exceptions.render_errors import (
    EscenaVaciaError,
    RenderFallidoError,
)


def _n(valor) -> str:
    return "%.2f" % float(valor)


class MotorNaked3D:
    """Genera el efecto de profundidad por parallax de capas."""

    def capacidades(self) -> dict:
        return {
            "capas": ("fondo", "medio", "frente"),
            "amplitudes_px": {"fondo": 0, "medio": 14, "frente": 28},
            "nota": "El frente sobresale del marco (efecto sin lentes)",
        }

    def generar(self, escena: Escena3D) -> bytes:
        if not isinstance(escena, Escena3D):
            raise ValueError("Se esperaba una Escena3D.")
        if not escena.es_renderizable:
            raise EscenaVaciaError("La escena no tiene objetos.")
        grupos = escena.objetos_por_capa()
        if not any(grupos.values()):
            raise RenderFallidoError("La escena no tiene objetos en ninguna capa.")
        ancho, alto = escena.ancho, escena.alto
        partes = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
            % (ancho, alto, ancho, alto),
            '<defs><linearGradient id="cielo" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#0B1220"/><stop offset="1" stop-color="#1E293B"/>'
            '</linearGradient></defs>',
            '<rect width="%s" height="%s" fill="url(#cielo)"/>' % (_n(ancho), _n(alto)),
        ]
        desplazamientos = {"fondo": 0.0, "medio": 14.0, "frente": 28.0}
        for capa in ("fondo", "medio", "frente"):
            objetos = grupos.get(capa, [])
            if not objetos:
                continue
            d = desplazamientos[capa]
            partes.append('<g data-capa="' + capa + '">')
            if d > 0:
                partes.append(
                    '<animateTransform attributeName="transform" attributeType="XML" '
                    'type="translate" values="0 0; %s 0; 0 0; -%s 0; 0 0" '
                    'dur="6s" repeatCount="indefinite" additive="sum"/>'
                    % (_n(d), _n(d))
                )
            for obj in objetos:
                partes.append(self._objeto(obj))
            partes.append('</g>')
        m = 14.0
        partes.append(
            '<rect x="%s" y="%s" width="%s" height="%s" fill="none" '
            'stroke="#38BDF8" stroke-width="6" rx="10"/>' % (
                _n(m), _n(m), _n(ancho - 2 * m), _n(alto - 2 * m),
            )
        )
        partes.append('</svg>')
        return "\n".join(partes).encode("utf-8")

    @staticmethod
    def _objeto(obj) -> str:
        forma = obj["forma"]
        color = obj["color"]
        if forma == "rect":
            return '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % (
                _n(obj["x"]), _n(obj["y"]), _n(obj["w"]), _n(obj["h"]), color)
        if forma == "circle":
            return '<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (
                _n(obj["cx"]), _n(obj["cy"]), _n(obj["r"]), color)
        return '<text x="%s" y="%s" fill="%s" font-size="24" font-family="sans-serif">%s</text>' % (
            _n(obj["x"]), _n(obj["y"]), color, obj["contenido"])
