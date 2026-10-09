"""Motor raster: PNG REAL con relleno solido y canal de PROFUNDIDAD.

Rasteriza rectangulos, circulos y texto (fuente bitmap 3x5) sobre
un buffer RGB usando slices por fila (rapido incluso en 4K).
La profundidad es un PNG en grises: fondo oscuro, frente claro.
"""
import math

from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.infrastructure.providers.font_bitmap import (
    ANCHO as GLIFO_ANCHO,
    ALTO as GLIFO_ALTO,
    texto_a_lineas,
)
from apps.laboratorio.infrastructure.providers.png_encoder import (
    encode_png_gray,
    encode_png_rgb,
)
from apps.laboratorio.shared.adapters.engine_adapter import AdaptadorMotor
from apps.laboratorio.shared.exceptions.render_errors import (
    EscenaVaciaError,
    RenderFallidoError,
)
from apps.laboratorio.shared.interfaces.renderer import Renderer, ResultadoRender

PROFUNDIDAD_POR_CAPA = {"fondo": 60, "medio": 150, "frente": 255}


def hex_a_rgb(color: str) -> tuple:
    """Convierte #RRGGBB a (r, g, b) enteros."""
    color = str(color).strip()
    if not color.startswith("#") or len(color) != 7:
        raise RenderFallidoError("Color invalido: " + repr(color))
    try:
        return (
            int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        )
    except ValueError as exc:
        raise RenderFallidoError("Color invalido: " + repr(color)) from exc


class RasterizadorBase:
    """Lienzo RGB + profundidad con operaciones por slice."""

    def __init__(self, ancho: int, alto: int, color_fondo: tuple):
        if ancho < 16 or alto < 16:
            raise RenderFallidoError("Dimensiones del lienzo invalidas.")
        self.w = int(ancho)
        self.h = int(alto)
        self.buf = bytearray(bytes(color_fondo) * (self.w * self.h))
        self.depth = bytearray(self.w * self.h)

    def _clip(self, x, y, w, h):
        x0 = max(0, int(x))
        y0 = max(0, int(y))
        x1 = min(self.w, int(x + w))
        y1 = min(self.h, int(y + h))
        return x0, y0, x1, y1

    def rect(self, x, y, w, h, color: tuple, depth_val: int) -> None:
        x0, y0, x1, y1 = self._clip(x, y, w, h)
        if x1 <= x0 or y1 <= y0:
            return
        fila = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            base = yy * self.w
            self.buf[(base + x0) * 3:(base + x1) * 3] = fila
            self.depth[base + x0:base + x1] = bytes([depth_val]) * (x1 - x0)

    def circle(self, cx, cy, r, color: tuple, depth_val: int) -> None:
        if r <= 0:
            return
        r = int(r)
        fila_color = None
        for dy in range(-r, r + 1):
            yy = int(cy) + dy
            if yy < 0 or yy >= self.h:
                continue
            half = int(math.sqrt(max(0.0, r * r - dy * dy)))
            x0 = max(0, int(cx) - half)
            x1 = min(self.w, int(cx) + half + 1)
            if x1 <= x0:
                continue
            if fila_color is None or len(fila_color) != (x1 - x0) * 3:
                fila_color = bytes(color) * (x1 - x0)
            base = yy * self.w
            self.buf[(base + x0) * 3:(base + x1) * 3] = fila_color
            self.depth[base + x0:base + x1] = bytes([depth_val]) * (x1 - x0)

    def texto(self, x, y, contenido: str, color: tuple, depth_val: int, escala: int = 2) -> None:
        """Rasteriza texto con la fuente 3x5 a la escala dada."""
        if escala < 1:
            raise RenderFallidoError("Escala de texto invalida.")
        px = x
        for caracter, patrones in texto_a_lineas(contenido):
            for fy, fila_bits in enumerate(patrones):
                for fx in range(GLIFO_ANCHO):
                    if not (fila_bits >> (GLIFO_ANCHO - 1 - fx)) & 1:
                        continue
                    self.rect(
                        px + fx * escala, y + fy * escala,
                        escala, escala, color, depth_val,
                    )
            px += (GLIFO_ANCHO + 1) * escala
            if px > self.w:
                break

    def imagen_png(self) -> bytes:
        """Codifica el lienzo RGB a PNG real."""
        return encode_png_rgb(self.w, self.h, bytes(self.buf))

    def profundidad_png(self) -> bytes:
        """Codifica el canal de profundidad a PNG en grises."""
        return encode_png_gray(self.w, self.h, bytes(self.depth))


class MotorRenderRaster(AdaptadorMotor, Renderer):
    """Calidad ALTA: PNG 1920x1080 con relleno solido + profundidad."""

    def __init__(self):
        AdaptadorMotor.__init__(self, "renderer_raster", "renderer", "1.0.0")
        self.marcar_disponible()

    def capacidades(self) -> dict:
        return {
            "calidades": ["alta"],
            "profundidad": True,
            "formato": "png",
            "texto": "fuente bitmap 3x5 real",
            "nota": "El canal de profundidad se produce como PNG en grises",
        }

    def renderizar(self, escena, opciones) -> ResultadoRender:
        if not isinstance(escena, Escena3D):
            raise RenderFallidoError("Se esperaba una Escena3D.")
        if not escena.es_renderizable:
            raise EscenaVaciaError("La escena no tiene objetos.")
        ancho = int(opciones.get("ancho", escena.ancho))
        alto = int(opciones.get("alto", escena.alto))
        lienzo = RasterizadorBase(ancho, alto, (15, 23, 42))
        sx = ancho / escena.ancho
        sy = alto / escena.alto
        escala_texto = max(2, int(round(min(sx, sy) * 2)))
        orden = ("fondo", "medio", "frente")
        for capa in orden:
            depth_val = PROFUNDIDAD_POR_CAPA[capa]
            for obj in escena.objetos:
                if obj.get("capa", "medio") != capa:
                    continue
                color = hex_a_rgb(obj["color"])
                if obj["forma"] == "rect":
                    lienzo.rect(
                        obj["x"] * sx, obj["y"] * sy,
                        obj["w"] * sx, obj["h"] * sy, color, depth_val,
                    )
                elif obj["forma"] == "circle":
                    lienzo.circle(
                        obj["cx"] * sx, obj["cy"] * sy,
                        obj["r"] * min(sx, sy), color, depth_val,
                    )
                else:
                    lienzo.texto(
                        obj["x"] * sx, obj["y"] * sy,
                        obj["contenido"], color, depth_val, escala_texto,
                    )
        return ResultadoRender(
            imagen_bytes=lienzo.imagen_png(),
            profundidad_bytes=lienzo.profundidad_png(),
            ancho=ancho,
            alto=alto,
            metadata={"formato": "png", "motor": "renderer_raster", "profundidad": True},
        )
