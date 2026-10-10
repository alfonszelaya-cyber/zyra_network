"""Motor de avatar desde foto: colores reales de TU foto."""
from apps.laboratorio.infrastructure.providers.png_decoder import (
    decodificar_png_rgb,
)


def _dominantes(pixeles: bytes, total: int) -> list:
    """Los 5 colores dominantes reales por bucketing."""
    cubetas = {}
    for i in range(0, total * 3, 3):
        clave = (pixeles[i] // 32, pixeles[i + 1] // 32, pixeles[i + 2] // 32)
        cubetas[clave] = cubetas.get(clave, 0) + 1
    ordenados = sorted(cubetas.items(), key=lambda kv: kv[1], reverse=True)
    colores = []
    for (cr, cg, cb), _ in ordenados[:5]:
        colores.append((cr * 32 + 16, cg * 32 + 16, cb * 32 + 16))
    return colores


def _tono_piel(pixeles: bytes, total: int) -> tuple:
    """Promedio de pixeles con razon piel (r > g > b, r claro)."""
    sr = sg = sb = n = 0
    for i in range(0, total * 3, 3):
        r, g, b = pixeles[i], pixeles[i + 1], pixeles[i + 2]
        if r > 120 and r > g > b and (r - b) > 15:
            sr += r
            sg += g
            sb += b
            n += 1
    if n < 10:
        return (234, 192, 154)
    return (sr // n, sg // n, sb // n)


def _hex(color: tuple) -> str:
    return "#%02X%02X%02X" % color


class MotorAvatar:
    """Genera un avatar SVG animado desde una foto real."""

    def capacidades(self) -> dict:
        return {
            "entrada": "foto PNG capturada por el sistema",
            "salida": "avatar SVG con colores reales de la foto",
            "animacion": "correr con piernas y brazos (SMIL)",
        }

    def generar(self, datos_png: bytes, nombre: str = "Avatar") -> bytes:
        ancho, alto, pixeles = decodificar_png_rgb(datos_png)
        total = ancho * alto
        paso = max(1, total // 20000)
        muestra = bytearray()
        for i in range(0, total, paso):
            muestra += pixeles[i * 3:(i + 1) * 3]
        m_total = len(muestra) // 3
        dominantes = _dominantes(muestra, m_total)
        piel = _tono_piel(muestra, m_total)
        ropa = dominantes[1] if len(dominantes) > 1 else dominantes[0]
        pelo = min(dominantes, key=lambda c: sum(c))
        pantalon = dominantes[2] if len(dominantes) > 2 else (40, 55, 80)
        cx = 150.0
        partes = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400" viewBox="0 0 300 400">',
            '<rect width="300" height="400" fill="#0B1220"/>',
            '<text x="150" y="34" text-anchor="middle" fill="#94A3B8" '
            'font-size="16" font-family="sans-serif">' + nombre[:60] + '</text>',
            '<line x1="0" y1="360" x2="300" y2="360" stroke="#1E293B" stroke-width="3"/>',
            '<g>',
            '<animateTransform attributeName="transform" attributeType="XML" '
            'type="translate" values="-80,0; 380,0" dur="6s" repeatCount="indefinite"/>',
            '<rect x="' + str(cx - 9) + '" y="290" width="10" height="60" rx="4" '
            'fill="' + _hex(pantalon) + '">'
            '<animateTransform attributeName="transform" type="rotate" '
            'values="28 ' + str(cx - 4) + ' 290; -28 ' + str(cx - 4) + ' 290; 28 '
            + str(cx - 4) + ' 290" dur="0.5s" repeatCount="indefinite"/></rect>',
            '<rect x="' + str(cx + 1) + '" y="290" width="10" height="60" rx="4" '
            'fill="' + _hex(pantalon) + '">'
            '<animateTransform attributeName="transform" type="rotate" '
            'values="-28 ' + str(cx + 6) + ' 290; 28 ' + str(cx + 6) + ' 290; -28 '
            + str(cx + 6) + ' 290" dur="0.5s" repeatCount="indefinite"/></rect>',
            '<rect x="' + str(cx - 22) + '" y="205" width="10" height="70" rx="4" '
            'fill="' + _hex(ropa) + '">'
            '<animateTransform attributeName="transform" type="rotate" '
            'values="-35 ' + str(cx - 17) + ' 210; 35 ' + str(cx - 17) + ' 210; -35 '
            + str(cx - 17) + ' 210" dur="0.5s" repeatCount="indefinite"/></rect>',
            '<rect x="' + str(cx + 12) + '" y="205" width="10" height="70" rx="4" '
            'fill="' + _hex(ropa) + '">'
            '<animateTransform attributeName="transform" type="rotate" '
            'values="35 ' + str(cx + 17) + ' 210; -35 ' + str(cx + 17) + ' 210; 35 '
            + str(cx + 17) + ' 210" dur="0.5s" repeatCount="indefinite"/></rect>',
            '<rect x="' + str(cx - 20) + '" y="160" width="40" height="100" rx="12" '
            'fill="' + _hex(ropa) + '"/>',
            '<circle cx="' + str(cx) + '" cy="120" r="34" fill="' + _hex(piel) + '"/>',
            '<path d="M ' + str(cx - 34) + ' 112 A 34 34 0 0 1 ' + str(cx + 34) + ' 112 '
            'L ' + str(cx + 34) + ' 100 A 34 26 0 0 0 ' + str(cx - 34) + ' 100 Z" '
            'fill="' + _hex(pelo) + '"/>',
            '<circle cx="' + str(cx - 12) + '" cy="124" r="3.5" fill="#1E293B"/>',
            '<circle cx="' + str(cx + 12) + '" cy="124" r="3.5" fill="#1E293B"/>',
            '<path d="M ' + str(cx - 10) + ' 138 Q ' + str(cx) + ' 146 ' + str(cx + 10) + ' 138" '
            'stroke="#1E293B" stroke-width="2" fill="none"/>',
            '</g>',
            '</svg>',
        ]
        return "\n".join(partes).encode("utf-8")
