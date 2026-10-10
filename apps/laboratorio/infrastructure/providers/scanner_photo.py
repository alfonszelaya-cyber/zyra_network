"""Motor de escaneo por foto: analisis REAL y determinista."""
import base64
import binascii

from apps.laboratorio.infrastructure.providers.png_decoder import (
    decodificar_png_rgb,
)

UMBRAL_BORDE = 30
GRID_ESQUINAS = 6
MAX_PUNTOS = 400


def foto_desde_entrada(contenido_b64: str) -> bytes:
    """Decodifica el contenido base64 de una entrada foto/escaneo."""
    if not isinstance(contenido_b64, str) or not contenido_b64.strip():
        raise ValueError("La entrada no tiene datos de foto.")
    crudo = contenido_b64.strip()
    if "," in crudo and crudo.startswith("data:"):
        crudo = crudo.split(",", 1)[1]
    try:
        return base64.b64decode(crudo, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Base64 de la foto invalido.") from exc


class MotorEscaneoFoto:
    """Escanea una foto y produce estructura real."""

    def capacidades(self) -> dict:
        return {
            "entrada": "foto PNG capturada por el sistema",
            "salidas": ("luminancia", "bordes", "esquinas", "profundidad_estimada", "malla"),
            "alcance": "estructura monocular de una foto; multi-vista usa N fotos",
        }

    def escanear(self, datos_png: bytes) -> dict:
        ancho, alto, pixeles = decodificar_png_rgb(datos_png)
        paso_l = max(1, min(ancho, alto) // 120)
        lw = max(2, ancho // paso_l)
        lh = max(2, alto // paso_l)
        lum = [[0] * lw for _ in range(lh)]
        for ly in range(lh):
            for lx in range(lw):
                px = min(ancho - 1, lx * paso_l)
                py = min(alto - 1, ly * paso_l)
                i = (py * ancho + px) * 3
                r, g, b = pixeles[i], pixeles[i + 1], pixeles[i + 2]
                lum[ly][lx] = round(0.299 * r + 0.587 * g + 0.114 * b)
        bordes = []
        for ly in range(1, lh - 1):
            for lx in range(1, lw - 1):
                gx = lum[ly][lx + 1] - lum[ly][lx - 1]
                gy = lum[ly + 1][lx] - lum[ly - 1][lx]
                mag = abs(gx) + abs(gy)
                if mag > UMBRAL_BORDE:
                    bordes.append([lx * paso_l, ly * paso_l, min(255, mag)])
        celdas_w = max(1, lw // GRID_ESQUINAS)
        celdas_h = max(1, lh // GRID_ESQUINAS)
        esquinas = []
        for cy in range(GRID_ESQUINAS):
            for cx in range(GRID_ESQUINAS):
                mejor = None
                for ly in range(cy * celdas_h, min(lh - 1, (cy + 1) * celdas_h)):
                    for lx in range(cx * celdas_w, min(lw - 1, (cx + 1) * celdas_w)):
                        respuesta = 0
                        centro = lum[ly][lx]
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            respuesta += abs(centro - lum[ly + dy][lx + dx]) ** 2
                        if mejor is None or respuesta > mejor[0]:
                            mejor = (respuesta, lx, ly)
                if mejor and mejor[0] > 100:
                    esquinas.append({
                        "x": mejor[1] * paso_l,
                        "y": mejor[2] * paso_l,
                        "respuesta": mejor[0],
                    })
        esquinas.sort(key=lambda e: e["respuesta"], reverse=True)
        esquinas = esquinas[:8]
        puntos = []
        paso_p = max(1, len(bordes) // MAX_PUNTOS) if bordes else 1
        for i, borde in enumerate(bordes):
            if i % paso_p == 0:
                puntos.append(borde)
        prof = []
        for borde in puntos:
            prof.append(round((borde[1] / max(1, alto - 1)) * 100.0, 2))
        return {
            "dimensiones": [ancho, alto],
            "total_bordes": len(bordes),
            "esquinas": esquinas,
            "malla": puntos[:MAX_PUNTOS],
            "profundidad_estimada": prof[:MAX_PUNTOS],
            "metodo": "luminancia + gradiente + Moravec en grid + perspectiva",
        }
