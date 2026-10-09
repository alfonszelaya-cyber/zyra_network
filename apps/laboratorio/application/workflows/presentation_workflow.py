"""Workflow de presentacion: slideshow SVG real y auto-avanzado."""

from apps.laboratorio.infrastructure.security.html_sanitizer import escapar


def _n(valor) -> str:
    return "%.2f" % float(valor)


def slideshow_svg(titulo: str, diapositivas: list) -> bytes:
    """Genera un slideshow SVG con avance automatico por duracion."""
    if not diapositivas:
        raise ValueError("El slideshow requiere al menos una diapositiva.")
    ancho, alto = 960, 540
    acumulado = 0.0
    grupos = []
    for i, d in enumerate(diapositivas):
        dur = max(1.0, min(300.0, float(d["duracion_s"])))
        grupos.append({
            "inicio": acumulado,
            "titulo": escapar(titulo),
            "nombre": escapar(d.get("nombre", "")),
            "narracion": escapar(d.get("narracion", "")),
            "objetos": d["svg"].get("objetos", []),
            "indice": i,
        })
        acumulado += dur
    partes = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
        % (ancho, alto, ancho, alto),
        '<rect width="%d" height="%d" fill="#0B1220"/>' % (ancho, alto),
        '<text x="%d" y="34" text-anchor="middle" fill="#F8FAFC" '
        'font-size="20" font-family="sans-serif">%s</text>' % (ancho // 2, escapar(titulo)),
    ]
    sx, sy = ancho / 800.0, alto / 600.0
    for g in grupos:
        partes.append('<g style="opacity:0">')
        partes.append(
            '<set attributeName="opacity" to="1" begin="%ss" fill="freeze"/>'
            % _n(g["inicio"])
        )
        for obj in g["objetos"]:
            partes.append(_objeto(obj, sx, sy))
        partes.append(
            '<text x="24" y="%d" fill="#93C5FD" font-size="16" '
            'font-family="sans-serif">%s · %d/%d</text>'
            % (alto - 24, g["nombre"], g["indice"] + 1, len(grupos))
        )
        if g["narracion"]:
            partes.append(
                '<text x="24" y="%d" fill="#94A3B8" font-size="13" '
                'font-family="sans-serif">%s</text>'
                % (alto - 8, g["narracion"])
            )
        partes.append('</g>')
    partes.append('</svg>')
    return "\n".join(partes).encode("utf-8")


def _objeto(obj, sx, sy) -> str:
    color = escapar(obj.get("color", "#64748B"))
    if obj.get("forma") == "rect":
        return '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % (
            _n(float(obj.get("x", 0)) * sx), _n(float(obj.get("y", 0)) * sy),
            _n(float(obj.get("w", 10)) * sx), _n(float(obj.get("h", 10)) * sy), color)
    if obj.get("forma") == "circle":
        return '<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (
            _n(float(obj.get("cx", 0)) * sx), _n(float(obj.get("cy", 0)) * sy),
            _n(float(obj.get("r", 10)) * min(sx, sy)), color)
    return '<text x="%s" y="%s" fill="%s" font-size="22" font-family="sans-serif">%s</text>' % (
        _n(float(obj.get("x", 0)) * sx), _n(float(obj.get("y", 20)) * sy),
        color, escapar(obj.get("contenido", "")))
