"""Motor OLIGRAMA: diagrama de nodos y flujo (mapa ZYRA).

Genera el diagrama oficial del ecosistema: ZYRA al centro y las
apps especializadas en anillo, con aristas de flujo animadas
(dash en movimiento) y pulso en el hub. Base para presentar la
red completa.
"""
import math

HUB = ("ZYRA", "#22D3EE")
ANILLO = (
    ("NEXO", "#2563EB"),
    ("AGRO", "#059669"),
    ("SEMILLA", "#F59E0B"),
    ("MPE", "#8B5CF6"),
    ("AXIS", "#EF4444"),
    ("SUBASTAS", "#EC4899"),
    ("CICLO-DIGITAL", "#14B8A6"),
    ("LABORATORIO", "#38BDF8"),
)
ARISTAS_EXTRA = (("SUBASTAS", "NEXO"),)


class MotorOligrama:
    def capacidades(self) -> dict:
        return {
            "hub": HUB[0],
            "nodos": [n for n, _ in ANILLO],
            "flujo_animado": True,
        }

    def generar(self, escena) -> bytes:
        ancho, alto = 900, 700
        cx, cy = ancho / 2.0, alto / 2.0
        radio = min(ancho, alto) * 0.34
        posiciones = {HUB[0]: (cx, cy)}
        for i, (nombre, _) in enumerate(ANILLO):
            ang = (2.0 * math.pi * i / len(ANILLO)) - math.pi / 2.0
            posiciones[nombre] = (
                cx + radio * math.cos(ang), cy + radio * math.sin(ang)
            )
        partes = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
            % (ancho, alto, ancho, alto),
            '<rect width="%d" height="%d" fill="#0B1220"/>' % (ancho, alto),
            '<defs><marker id="punta" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            '<path d="M 0 0 L 10 5 L 0 10 z" fill="#38BDF8"/></marker></defs>',
        ]
        for destino, _ in ANILLO:
            partes.append(self._arista(cx, cy, *posiciones[destino]))
        for origen, destino in ARISTAS_EXTRA:
            partes.append(self._arista(*posiciones[origen], *posiciones[destino]))
        for nombre, color in ANILLO:
            x, y = posiciones[nombre]
            partes.append(self._nodo(x, y, nombre, color, 40.0, 15.0))
        partes.append(self._nodo(cx, cy, HUB[0], HUB[1], 58.0, 18.0, pulso=True))
        if escena is not None and getattr(escena, "nombre", ""):
            partes.append(
                '<text x="%d" y="36" text-anchor="middle" fill="#94A3B8" '
                'font-size="18" font-family="sans-serif">%s</text>' % (
                    ancho // 2, escena.nombre)
            )
        partes.append('</svg>')
        return "\n".join(partes).encode("utf-8")

    @staticmethod
    def _arista(x1, y1, x2, y2) -> str:
        return (
            '<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#38BDF8" '
            'stroke-width="1.6" opacity="0.65" stroke-dasharray="7 5" '
            'marker-end="url(#punta)">'
            '<animate attributeName="stroke-dashoffset" from="24" to="0" '
            'dur="1.6s" repeatCount="indefinite"/></line>' % (x1, y1, x2, y2)
        )

    @staticmethod
    def _nodo(x, y, nombre, color, radio, fuente, pulso=False) -> str:
        partes = ['<g>']
        if pulso:
            partes.append(
                '<circle cx="%.2f" cy="%.2f" r="%.2f" fill="none" stroke="%s" '
                'stroke-width="2" opacity="0.5">'
                '<animate attributeName="r" values="%.2f;%.2f;%.2f" dur="2.4s" repeatCount="indefinite"/>'
                '<animate attributeName="opacity" values="0.5;0;0.5" dur="2.4s" repeatCount="indefinite"/>'
                '</circle>' % (x, y, radio * 1.15, color, radio * 1.15, radio * 1.7, radio * 1.15)
            )
        partes.append(
            '<circle cx="%.2f" cy="%.2f" r="%.2f" fill="#0F172A" stroke="%s" '
            'stroke-width="3"/><circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s" '
            'opacity="0.35"/>' % (x, y, radio, color, x, y, radio * 0.55, color)
        )
        partes.append(
            '<text x="%.2f" y="%.2f" text-anchor="middle" fill="#E2E8F0" '
            'font-size="%s" font-family="sans-serif" font-weight="600">%s</text>' % (
                x, y + radio + fuente + 8, str(int(fuente)), nombre)
        )
        partes.append('</g>')
        return "\n".join(partes)
