"""Exportador SVG real: graficas de barras para evaluaciones."""

from apps.laboratorio.infrastructure.security.html_sanitizer import escapar

COLORES = {"A": "#2563EB", "B": "#059669", "C": "#D97706"}
COLOR_DEFECTO = "#64748B"
ANCHO = 800
ALTO = 480
MARGEN = 60


def _n(valor) -> str:
    return "%.2f" % float(valor)


def _fmt1(valor) -> str:
    return "%.1f" % float(valor)


def evaluaciones_a_barras(evaluaciones: list) -> list:
    barras = []
    for e in evaluaciones:
        puntaje = (e.get("metricas") or {}).get("puntaje_total", 0.0)
        try:
            puntaje = round(float(puntaje), 2)
        except (TypeError, ValueError):
            puntaje = 0.0
        tipo = str(e.get("tipo", "?")).upper()
        barras.append({
            "etiqueta": "Escenario " + tipo,
            "valor": puntaje,
            "color": COLORES.get(tipo, COLOR_DEFECTO),
        })
    return barras


def grafica_barras(titulo: str, barras: list) -> bytes:
    if not isinstance(titulo, str):
        raise ValueError("titulo debe ser texto.")
    if not isinstance(barras, list):
        raise ValueError("barras debe ser lista.")
    rect_fondo = '<rect width="100' + chr(37) + '" height="100' + chr(37) + '" fill="#0F172A"/>'
    partes = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (ANCHO, ALTO, ANCHO, ALTO),
        rect_fondo,
        '<text x="%d" y="40" text-anchor="middle" fill="#F8FAFC" font-size="22" font-family="sans-serif">%s</text>' % (ANCHO // 2, escapar(titulo)),
    ]
    if not barras:
        partes.append(
            '<text x="%d" y="%d" text-anchor="middle" fill="#94A3B8" '
            'font-size="16" font-family="sans-serif">Sin evaluaciones todavia</text>'
            % (ANCHO // 2, ALTO // 2)
        )
    else:
        area_ancho = ANCHO - 2 * MARGEN
        area_alto = ALTO - 2 * MARGEN - 20
        total = len(barras)
        ancho_barra = min(120.0, area_ancho / total * 0.6)
        paso = area_ancho / total
        for i, barra in enumerate(barras):
            valor = max(0.0, min(100.0, float(barra["valor"])))
            altura = area_alto * (valor / 100.0)
            x = MARGEN + i * paso + (paso - ancho_barra) / 2
            y = MARGEN + (area_alto - altura)
            centro = x + ancho_barra / 2
            partes.append('<rect x="%s" y="%s" width="%s" height="%s" fill="%s" rx="6"/>' % (
                _n(x), _n(y), _n(ancho_barra), _n(altura), escapar(barra["color"])))
            partes.append('<text x="%s" y="%s" text-anchor="middle" fill="#E2E8F0" font-size="14" font-family="sans-serif">%s</text>' % (
                _n(centro), _n(y - 8), escapar(_fmt1(barra["valor"]))))
            partes.append('<text x="%s" y="%d" text-anchor="middle" fill="#94A3B8" font-size="13" font-family="sans-serif">%s</text>' % (
                _n(centro), ALTO - MARGEN + 20, escapar(barra["etiqueta"])))
    partes.append('</svg>')
    return "\n".join(partes).encode("utf-8")
