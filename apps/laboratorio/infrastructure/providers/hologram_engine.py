"""Motor HOLOGRAMA: proyeccion volumetrica estilizada en SVG.

Base emisora con glow, haz cónico con gradiente, figura flotante
con pulso y particulas ascendentes. Es la estetica de holograma
real producida de forma generativa y verificable.
"""
from apps.laboratorio.domain.scene import Escena3D


def _n(valor) -> str:
    return "%.2f" % float(valor)


class MotorHolograma:
    def capacidades(self) -> dict:
        return {
            "elementos": ("base_emisora", "haz_conico", "figura_glow", "particulas"),
            "paleta": ("#22D3EE", "#38BDF8", "#67E8F9"),
        }

    def generar(self, escena: Escena3D) -> bytes:
        if not isinstance(escena, Escena3D):
            raise ValueError("Se esperaba una Escena3D.")
        ancho, alto = max(escena.ancho, 480), max(escena.alto, 480)
        cx = ancho / 2.0
        base_y = alto - 60.0
        apex_y = alto * 0.28
        fig_cx = cx
        fig_cy = (apex_y + base_y) / 2.0
        partes = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
            % (ancho, alto, ancho, alto),
            '<defs>',
            '<radialGradient id="glowBase" cx="0.5" cy="0.5" r="0.5">'
            '<stop offset="0" stop-color="#22D3EE" stop-opacity="0.9"/>'
            '<stop offset="1" stop-color="#22D3EE" stop-opacity="0"/></radialGradient>',
            '<linearGradient id="haz" x1="0" y1="1" x2="0" y2="0">'
            '<stop offset="0" stop-color="#22D3EE" stop-opacity="0.45"/>'
            '<stop offset="1" stop-color="#22D3EE" stop-opacity="0.02"/></linearGradient>',
            '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">'
            '<feGaussianBlur stdDeviation="5" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
            '</defs>',
            '<rect width="%s" height="%s" fill="#020617"/>' % (_n(ancho), _n(alto)),
            '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="url(#glowBase)">'
            '<animate attributeName="rx" values="%s;%s;%s" dur="3s" repeatCount="indefinite"/>'
            '</ellipse>' % (_n(cx), _n(base_y), _n(ancho * 0.32), _n(24.0),
                            _n(ancho * 0.32), _n(ancho * 0.38), _n(ancho * 0.32)),
            '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="none" stroke="#38BDF8" stroke-width="2"/>'
            % (_n(cx), _n(base_y), _n(ancho * 0.22), _n(14.0)),
            '<polygon points="%s,%s %s,%s %s,%s %s,%s" fill="url(#haz)">' % (
                _n(cx - ancho * 0.24), _n(base_y), _n(cx + ancho * 0.24), _n(base_y),
                _n(cx + ancho * 0.08), _n(apex_y), _n(cx - ancho * 0.08), _n(apex_y),
            ),
            '<g filter="url(#glow)">',
            '<animate attributeName="opacity" values="0.75;1;0.75" dur="2.4s" repeatCount="indefinite"/>',
            '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="#67E8F9" stroke-width="2.5"/>' % (
                _n(fig_cx), _n(fig_cy - 46), _n(22.0)),
            '<rect x="%s" y="%s" width="%s" height="%s" rx="10" fill="none" stroke="#67E8F9" stroke-width="2.5"/>' % (
                _n(fig_cx - 26), _n(fig_cy - 18), _n(52.0), _n(78.0)),
            '</g>',
        ]
        for i in range(7):
            px = cx + (i - 3) * (ancho * 0.055)
            dur = 2.6 + (i % 4) * 0.7
            retardo = i * 0.4
            partes.append(
                '<circle cx="%s" cy="%s" r="2.5" fill="#67E8F9" opacity="0.85">'
                '<animate attributeName="cy" values="%s;%s" dur="%ss" begin="%ss" repeatCount="indefinite"/>'
                '<animate attributeName="opacity" values="0.85;0" dur="%ss" begin="%ss" repeatCount="indefinite"/>'
                '</circle>' % (_n(px), _n(base_y - 8), _n(base_y - 8), _n(apex_y + 30),
                               ("%.1f" % dur), ("%.1f" % retardo),
                               ("%.1f" % dur), ("%.1f" % retardo))
            )
        if escena.nombre:
            partes.append(
                '<text x="%s" y="%s" text-anchor="middle" fill="#A5F3FC" '
                'font-size="20" font-family="sans-serif" opacity="0.9">%s</text>' % (
                    _n(cx), _n(40.0), escena.nombre)
            )
        partes.append('</svg>')
        return "\n".join(partes).encode("utf-8")
